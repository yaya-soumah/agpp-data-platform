import pytest

from pydantic import ValidationError

from src.shared.configuration.environment import Environment
from src.shared.configuration.service import ConfigurationService
from src.shared.exceptions import ConfigurationError


@pytest.fixture
def base_yaml() -> str:
    return """
    application:
      name: AGPP Data Platform
      version: 0.1.0
    
    environment:
      timezone: UTC
    
    pipeline:
      batch_size: 1000
      retry_attempts: 3
    
    warehouse:
      schema: analytics
    
    database:
      port: 5432
      pool_size: 10
      connection_timeout: 30
    
    paths:
      raw_data: data/raw
      processed_data: data/processed
      archive_data: data/archive
    
    features:
      enable_metrics: false
      enable_profiling: false
    """

@pytest.fixture
def development_yaml() -> str:
    return """
    database:
      pool_size: 5
    
    pipeline:
      retry_attempts: 1
    """

@pytest.fixture
def logging_yaml() -> str:
    return """
    logging:
      version: 1
      format:
        standard: "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    
      handlers:
        console:
          enabled: true
    
        file:
          enabled: true
          path: logs/agpp.log
    
      development:
        level: DEBUG
    
      testing:
        level: WARNING
    
      production:
        level: INFO
    """
    
def test_load_development_configuration(tmp_path, base_yaml, development_yaml, logging_yaml):
    (tmp_path / "base.yaml").write_text(
        base_yaml,
        encoding="utf-8",
    )

    (tmp_path / "development.yaml").write_text(
        development_yaml,
        encoding="utf-8",
    )

    (tmp_path / "logging.yaml").write_text(
        logging_yaml,
        encoding="utf-8",
    )

    service = ConfigurationService(tmp_path)

    configuration = service.load(Environment.DEVELOPMENT)

    assert configuration.app.environment_name == Environment.DEVELOPMENT
    assert configuration.app.database.pool_size == 5
    assert configuration.app.database.port == 5432
    assert configuration.app.database.connection_timeout == 30
    assert configuration.app.pipeline.retry_attempts == 1
    assert configuration.app.pipeline.batch_size == 1000

    assert configuration.logging.development.level == "DEBUG"

def test_load_injects_environment_name(tmp_path, base_yaml, development_yaml, logging_yaml):
    (tmp_path / "base.yaml").write_text(
            base_yaml,
            encoding="utf-8",
        )
    
    (tmp_path / "development.yaml").write_text(
            development_yaml,
            encoding="utf-8",
        )
    
    (tmp_path / "logging.yaml").write_text(
            logging_yaml,
            encoding="utf-8",
        )
    
    service = ConfigurationService(tmp_path)

    configuration = service.load(Environment.DEVELOPMENT)

    assert configuration.app.environment_name is Environment.DEVELOPMENT


def test_reject_invalid_app_configuration(tmp_path, base_yaml, development_yaml, logging_yaml):


  (tmp_path / "base.yaml").write_text(
      """
database:
  pool_size: -1
""", encoding="utf-8"
  )
  (tmp_path / "development.yaml").write_text(
      development_yaml, encoding="utf-8"
  )
  (tmp_path / "logging.yaml").write_text(
      logging_yaml, encoding="utf-8"
  )

  service = ConfigurationService(tmp_path)

  with pytest.raises(ConfigurationError) as exc:
      service.load(Environment.DEVELOPMENT)

  assert exc.value.error_code == "CONFIG_VALIDATION_ERROR"
  assert isinstance(
      exc.value.__cause__, ValidationError
  )

def test_reject_invalid_logging_configuration(tmp_path, base_yaml, development_yaml, logging_yaml):


  (tmp_path / "base.yaml").write_text(
      base_yaml, encoding="utf-8"
  )
  (tmp_path / "development.yaml").write_text(
      development_yaml, encoding="utf-8"
  )
  (tmp_path / "logging.yaml").write_text(
      """
      logging:
        development:
          level: BANANA
      """, encoding="utf-8"
  )

  service = ConfigurationService(tmp_path)

  with pytest.raises(ConfigurationError) as exc:
      service.load(Environment.DEVELOPMENT)

  assert exc.value.error_code == "CONFIG_VALIDATION_ERROR"
  assert isinstance(
      exc.value.__cause__, ValidationError
  )

def test_configuration_is_immutable(
    tmp_path,
    base_yaml,
    development_yaml,
    logging_yaml,
):
    (tmp_path / "base.yaml").write_text(
        base_yaml,
        encoding="utf-8",
    )

    (tmp_path / "development.yaml").write_text(
        development_yaml,
        encoding="utf-8",
    )

    (tmp_path / "logging.yaml").write_text(
        logging_yaml,
        encoding="utf-8",
    )

    service = ConfigurationService(tmp_path)

    configuration = service.load(Environment.DEVELOPMENT)

    with pytest.raises(ValidationError):
        configuration.app.database.pool_size = 10

def test_reject_missing_logging_section(
    tmp_path,
    base_yaml,
    development_yaml,
):
    (tmp_path / "base.yaml").write_text(
        base_yaml,
        encoding="utf-8",
    )

    (tmp_path / "development.yaml").write_text(
        development_yaml,
        encoding="utf-8",
    )

    (tmp_path / "logging.yaml").write_text(
        """
        version: 1
        """,
        encoding="utf-8",
    )

    service = ConfigurationService(tmp_path)

    with pytest.raises(ConfigurationError) as exc:
        service.load(Environment.DEVELOPMENT)

    assert exc.value.error_code == "CONFIG_MISSING_SECTION"

    assert isinstance(
        exc.value.__cause__ , KeyError
    )

def test_load_resolves_environment_from_runtime(
    tmp_path,
    base_yaml,
    development_yaml,
    logging_yaml,
    monkeypatch,
):
    (tmp_path / "base.yaml").write_text(
        base_yaml,
        encoding="utf-8",
    )

    (tmp_path / "development.yaml").write_text(
        development_yaml,
        encoding="utf-8",
    )

    (tmp_path / "logging.yaml").write_text(
        logging_yaml,
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "AGPP_ENV",
        "development",
    )

    service = ConfigurationService(tmp_path)

    configuration = service.load()

    assert configuration.app.environment_name is Environment.DEVELOPMENT
    assert configuration.app.database.pool_size == 5


def test_load_rejects_missing_runtime_environment(
    tmp_path,
    base_yaml,
    development_yaml,
    logging_yaml,
    monkeypatch,
):
    (tmp_path / "base.yaml").write_text(
        base_yaml,
        encoding="utf-8",
    )

    (tmp_path / "development.yaml").write_text(
        development_yaml,
        encoding="utf-8",
    )

    (tmp_path / "logging.yaml").write_text(
        logging_yaml,
        encoding="utf-8",
    )

    monkeypatch.delenv(
        "AGPP_ENV",
        raising=False,
    )

    service = ConfigurationService(tmp_path)

    with pytest.raises(ConfigurationError) as exc:
        service.load()

    assert (
        exc.value.error_code
        == "CONFIG_ENVIRONMENT_NOT_SET"
    )

def test_explicit_environment_does_not_require_runtime_environment(
    tmp_path,
    base_yaml,
    development_yaml,
    logging_yaml,
    monkeypatch,
):
    (tmp_path / "base.yaml").write_text(
        base_yaml,
        encoding="utf-8",
    )

    (tmp_path / "development.yaml").write_text(
        development_yaml,
        encoding="utf-8",
    )

    (tmp_path / "logging.yaml").write_text(
        logging_yaml,
        encoding="utf-8",
    )

    monkeypatch.delenv(
        "AGPP_ENV",
        raising=False,
    )

    service = ConfigurationService(tmp_path)

    configuration = service.load(
        Environment.DEVELOPMENT
    )

    assert configuration.app.environment_name is Environment.DEVELOPMENT

def test_runtime_environment_selects_environment_configuration(
    tmp_path,
    base_yaml,
    development_yaml,
    logging_yaml,
    monkeypatch,
):
    (tmp_path / "base.yaml").write_text(
        base_yaml,
        encoding="utf-8",
    )

    (tmp_path / "development.yaml").write_text(
        development_yaml,
        encoding="utf-8",
    )

    (tmp_path / "testing.yaml").write_text(
        """
pipeline:
  batch_size: 100

database:
  pool_size: 2
""",
        encoding="utf-8",
    )

    (tmp_path / "logging.yaml").write_text(
        logging_yaml,
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "AGPP_ENV",
        "testing",
    )

    service = ConfigurationService(tmp_path)

    configuration = service.load()

    assert configuration.app.environment_name is Environment.TESTING
    assert configuration.app.pipeline.batch_size == 100
    assert configuration.app.database.pool_size == 2