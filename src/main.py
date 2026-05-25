"""Electricity Status Telegram Bot - Main Entry Point."""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from config.loader import load_config, Config, ConfigValidationError
from config.watcher import ConfigWatcher
from monitor.state_machine import StateMachine, ElectricityStatus
from monitor.tcp_checker import TCPChecker
from storage.events import EventStore
from notifier.push_notifier import PushNotifier
from bot.handlers import cmd_status, cmd_stats, cmd_reload, cmd_help, handle_callback


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class BotContext:
    """Holds all bot runtime context."""

    def __init__(self):
        self.config: Config = None
        self.bot: Bot = None
        self.dispatcher: Dispatcher = None
        self.storage = MemoryStorage()
        self.state_machine: StateMachine = None
        self.event_store: EventStore = None
        self.notifier: PushNotifier = None
        self.config_watcher: ConfigWatcher = None
        self._poll_task: asyncio.Task = None
        self._running = False


context = BotContext()


async def initialize_bot():
    """Initialize all bot components."""
    # Load configuration
    try:
        context.config = load_config()
    except FileNotFoundError:
        logger.error("Configuration file not found: config.yaml")
        logger.error("Please create config.yaml from config.yaml.example and restart.")
        return False
    except ConfigValidationError as e:
        logger.error("Invalid configuration: %s", e)
        logger.error("Please check config.yaml and restart.")
        return False

    # Validate bot token
    if not context.config.has_valid_token():
        logger.error("Invalid or missing bot token in config.yaml.")
        logger.error("Set 'bot.token' to your bot's API token from @BotFather.")
        return False

    # Initialize bot and dispatcher
    context.bot = Bot(token=context.config.bot_token)
    context.dispatcher = Dispatcher(storage=context.storage)

    # Initialize state machine
    context.state_machine = StateMachine(last_state_file=context.config.last_state_file)
    context.state_machine.initialize_from_file()

    # Initialize event store
    context.event_store = EventStore(db_path=context.config.db_path)
    await context.event_store.initialize()

    # Initialize notifier
    context.notifier = PushNotifier(
        bot=context.bot,
        admin_user_ids=context.config.admin_user_ids
    )

    # Set up status change callback
    async def on_status_change(new_status: ElectricityStatus, previous_status):
        if new_status in (ElectricityStatus.ON, ElectricityStatus.OFF):
            await context.notifier.notify_status_change(new_status.value)

    # Register handlers
    register_handlers(context.dispatcher)

    # Start config watcher
    context.config_watcher = ConfigWatcher(Path("config.yaml"))
    await context.config_watcher.start(on_config_changed)

    logger.info("Bot initialized successfully.")
    return True


def register_handlers(dispatcher: Dispatcher):
    """Register all command and callback handlers."""
    # Command handlers
    dispatcher.message.register(cmd_status, Command("status"))
    dispatcher.message.register(cmd_stats, Command("stats"))
    dispatcher.message.register(cmd_reload, Command("reload"))
    dispatcher.message.register(cmd_help, Command("help"))

    # Callback query handler
    dispatcher.callback_query.register(handle_callback)


async def on_config_changed():
    """Handle configuration file changes."""
    try:
        new_config = load_config()

        # Check for device config changes (hot reload)
        if (new_config.device_host != context.config.device_host or
            new_config.device_port != context.config.device_port or
            new_config.poll_interval != context.config.poll_interval):
            logger.info("Device configuration changed, applying updates...")
            # Update config reference
            context.config = new_config
            # Signal polling task to restart with new interval
            if hasattr(context, '_poll_task') and context._poll_task:
                context._poll_task.cancel()

        # Check for bot config changes (require restart)
        if (new_config.bot_token != context.config.bot_token or
            set(new_config.admin_user_ids) != set(context.config.admin_user_ids)):
            logger.warning("Bot token or admin IDs changed. Changes require a bot restart.")
            logger.warning("Please restart the bot to apply bot configuration changes.")

        # Update notifier admin IDs
        if context.notifier:
            context.notifier.update_admin_ids(new_config.admin_user_ids)

        logger.info("Configuration reloaded successfully.")
    except ConfigValidationError as e:
        logger.error("Config reload failed: %s", e)
        logger.error("Retaining previous valid configuration.")


async def start_polling():
    """Start the TCP polling loop."""
    checker = TCPChecker(context.config.device_host, context.config.device_port)

    while context._running:
        try:
            # Perform TCP check
            result = await checker.check()

            # Process result through state machine
            new_status = await context.state_machine.process_check_result(result.success)

            # Log result
            if result.success:
                logger.info("TCP check successful to %s:%d (%.0fms)",
                           result.host, result.port, result.duration_ms)
            else:
                logger.warning("TCP check failed for %s:%d - %s",
                             result.host, result.port, result.error)

            # Notify on state change
            if new_status:
                logger.info("Status changed to: %s", new_status.value)
                await context.notifier.notify_status_change(new_status.value)

            # Wait for next poll interval
            poll_interval = context.config.poll_interval
            logger.debug("Waiting %d seconds for next poll...", poll_interval)
            await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            logger.info("Polling task cancelled.")
            break
        except Exception as e:
            logger.error("Error in polling loop: %s", e, exc_info=True)
            await asyncio.sleep(5)  # Brief backoff on error


async def graceful_shutdown():
    """Perform graceful shutdown."""
    logger.info("Shutting down bot...")
    context._running = False

    # Stop polling task
    if hasattr(context, '_poll_task') and context._poll_task:
        context._poll_task.cancel()
        try:
            await context._poll_task
        except asyncio.CancelledError:
            pass

    # Stop config watcher
    if context.config_watcher:
        await context.config_watcher.stop()

    # Save state
    if context.state_machine:
        context.state_machine.save_state()

    # Close event store
    if context.event_store:
        await context.event_store.close()

    # Close bot
    if context.bot:
        await context.bot.session.close()

    logger.info("Bot shut down gracefully.")


async def main():
    """Main application entry point."""
    global context

    # Initialize bot
    initialized = await initialize_bot()
    if not initialized:
        sys.exit(1)

    # Set up running state
    context._running = True

    # Start polling in background
    context._poll_task = asyncio.create_task(start_polling())

    # Start long polling
    logger.info("Starting bot long polling...")
    try:
        await context.dispatcher.start_polling(context.bot)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Polling error: %s", e, exc_info=True)
    finally:
        await graceful_shutdown()


if __name__ == "__main__":
    # Handle graceful shutdown on signals
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        loop.create_task(graceful_shutdown())
        loop.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        loop.run_until_complete(graceful_shutdown())
    finally:
        if loop.is_running():
            loop.close()