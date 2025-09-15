from importlib import reload

import utils.logging_config as logging_config


def test_log_file_rotation(tmp_path):
    reload(logging_config)
    log_dir = tmp_path / "logs"
    logger = logging_config.logger
    logger.remove()
    logger.add(
        log_dir / "agent_{time}.log", rotation="1 KB", retention="1 day", level="INFO"
    )
    for _ in range(200):
        logger.info("x" * 100)
    logger.remove()
    files = list(log_dir.glob("agent_*.log"))
    assert len(files) >= 2
    reload(logging_config)
