from pathlib import Path

import pytest
from pydantic import ValidationError
from src.pipelines.supplier_product.config import (
    APISourceConfig,
    CSVSourceConfig,
    FTPSourceConfig,
    SupplierProductConfig,
    SupplierProductSourceType,
    SupplierProductValidationConfig,
)
from src.shared.exceptions import ConfigurationError


@pytest.fixture
def csv_source() -> CSVSourceConfig:
    return CSVSourceConfig(
        name="supplier_products",
        type=SupplierProductSourceType.CSV,
        path=Path("supplier_products.csv"),
    )


@pytest.fixture
def api_source() -> APISourceConfig:
    return APISourceConfig(
        name="supplier_products",
        type=SupplierProductSourceType.API,
        url="https://www.example.com/api",
    )


@pytest.fixture
def ftp_source() -> FTPSourceConfig:
    return FTPSourceConfig(
        name="supplier_products_ftp",
        type=SupplierProductSourceType.FTP,
        host="ftp.supplier.example.com",
        port=21,
        username="supplier_user",
        password_env_var="SUPPLIER_FTP_PASSWORD",
        path="supplier_products.csv",
    )


class TestCSVSourceConfig:
    def test_valid_source_config(self, csv_source: CSVSourceConfig) -> None:

        assert csv_source.name == "supplier_products"
        assert csv_source.type == SupplierProductSourceType.CSV
        assert csv_source.path == Path("supplier_products.csv")

    def test_source_name_cannot_be_blank(self) -> None:
        with pytest.raises(ConfigurationError):
            CSVSourceConfig(
                name=" ",
                type=SupplierProductSourceType.CSV,
                path=Path("supplier_product.csv"),
            )

    def test_source_type_must_be_supported(self) -> None:
        with pytest.raises(ValidationError):
            CSVSourceConfig(
                name="supplier_products",
                type="json",
                path=Path("supplier_product.json"),
            )

    def test_valid_supplier_product_config(self) -> None:
        config = SupplierProductConfig(
            sources=[
                CSVSourceConfig(
                    name="supplier_master",
                    type=SupplierProductSourceType.CSV,
                    path=Path("supplier_master.csv"),
                ),
                CSVSourceConfig(
                    name="supplier_products",
                    type=SupplierProductSourceType.CSV,
                    path=Path("supplier_products.csv"),
                ),
            ],
            validation=SupplierProductValidationConfig(
                reject_invalid_rows=True,
            ),
        )

        assert len(config.sources) == 2
        assert config.validation.reject_invalid_rows is True


class TestSupplierProductConfig:
    def test_sources_cannot_be_empty(self) -> None:
        with pytest.raises(ValidationError):
            SupplierProductConfig(sources=[])

    def test_source_names_must_be_unique(self, csv_source: CSVSourceConfig) -> None:

        with pytest.raises(ConfigurationError, match="Source names must be unique."):
            SupplierProductConfig(
                sources=[csv_source, csv_source],
            )

    def test_validation_config_has_expected_default(
        self, csv_source: CSVSourceConfig
    ) -> None:
        config = SupplierProductConfig(
            sources=[
                csv_source,
            ]
        )

        assert config.validation.reject_invalid_rows is True

    def test_extra_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SupplierProductConfig(sources=[], unexpected="value")

    def test_configuration_is_immutable(self, csv_source: CSVSourceConfig) -> None:

        config = SupplierProductConfig(
            sources=[
                csv_source,
            ],
        )
        with pytest.raises(ValidationError):
            config.validation = SupplierProductValidationConfig(
                reject_invalid_rows=False,
            )


class TestFTPSourceConfig:
    def test_valid_ftp_source_configuration(self, ftp_source) -> None:

        assert ftp_source.name == "supplier_products_ftp"
        assert ftp_source.type is SupplierProductSourceType.FTP
        assert ftp_source.host == "ftp.supplier.example.com"
        assert ftp_source.port == 21
        assert ftp_source.username == "supplier_user"
        assert ftp_source.password_env_var == "SUPPLIER_FTP_PASSWORD"
        assert ftp_source.path.name == "supplier_products.csv"

    def test_ftp_source_uses_default_port(self) -> None:

        config = FTPSourceConfig(
            name="supplier_products_ftp",
            type=SupplierProductSourceType.FTP,
            host="ftp.supplier.example.com",
            username="supplier_user",
            password_env_var="SUPPLIER_FTP_PASSWORD",
            path="supplier_products.csv",
        )

        assert config.port == 21

    def test_ftp_source_accepts_custom_port(self) -> None:
        config = FTPSourceConfig(
            name="supplier_products_ftp",
            type=SupplierProductSourceType.FTP,
            host="ftp.supplier.example.com",
            port=2121,
            username="supplier_user",
            password_env_var="SUPPLIER_FTP_PASSWORD",
            path="supplier_products.csv",
        )

        assert config.port == 2121

    def test_ftp_source_rejects_blank_host(self) -> None:
        with pytest.raises(ConfigurationError, match="FTP host must not be blank"):
            FTPSourceConfig(
                name="supplier_products_ftp",
                type=SupplierProductSourceType.FTP,
                host="   ",
                username="supplier_user",
                password_env_var="SUPPLIER_FTP_PASSWORD",
                path="supplier_products.csv",
            )

    def test_ftp_source_rejects_blank_username(self) -> None:
        with pytest.raises(ConfigurationError, match="FTP username must not be blank"):
            FTPSourceConfig(
                name="supplier_products_ftp",
                type=SupplierProductSourceType.FTP,
                host="ftp.supplier.example.com",
                username="   ",
                password_env_var="SUPPLIER_FTP_PASSWORD",
                path="supplier_products.csv",
            )

    def test_ftp_source_rejects_blank_password_environment_variable(self) -> None:
        with pytest.raises(
            ConfigurationError,
            match="FTP password environment variable name must not be blank",
        ):
            FTPSourceConfig(
                name="supplier_products_ftp",
                type=SupplierProductSourceType.FTP,
                host="ftp.supplier.example.com",
                username="supplier_user",
                password_env_var="   ",
                path="supplier_products.csv",
            )

    def test_ftp_source_rejects_absolute_path(self) -> None:
        with pytest.raises(
            ConfigurationError,
            match="FTP source path must not be absolute.",
        ):
            FTPSourceConfig(
                name="supplier_products_ftp",
                type=SupplierProductSourceType.FTP,
                host="ftp.supplier.example.com",
                username="supplier_user",
                password_env_var="SUPPLIER_FTP_PASSWORD",
                path="/supplier_products.csv",
            )

    def test_ftp_source_rejects_invalid_port(self) -> None:
        with pytest.raises(ValidationError):
            FTPSourceConfig(
                name="supplier_products_ftp",
                type=SupplierProductSourceType.FTP,
                host="ftp.supplier.example.com",
                port=70000,
                username="supplier_user",
                password_env_var="SUPPLIER_FTP_PASSWORD",
                path="supplier_products.csv",
            )

    def test_supplier_product_config_accepts_ftp_source(self) -> None:
        config = SupplierProductConfig(
            sources=[
                FTPSourceConfig(
                    name="supplier_products_ftp",
                    type=SupplierProductSourceType.FTP,
                    host="ftp.supplier.example.com",
                    username="supplier_user",
                    password_env_var="SUPPLIER_FTP_PASSWORD",
                    path="supplier_products.csv",
                )
            ]
        )

        assert len(config.sources) == 1
        assert isinstance(config.sources[0], FTPSourceConfig)

    def test_supplier_product_config_accepts_csv_api_and_ftp_sources(self) -> None:
        config = SupplierProductConfig(
            sources=[
                CSVSourceConfig(
                    name="supplier_master",
                    type=SupplierProductSourceType.CSV,
                    path="supplier_master.csv",
                ),
                APISourceConfig(
                    name="supplier_products_api",
                    type=SupplierProductSourceType.API,
                    url="https://supplier.example.com/products",
                ),
                FTPSourceConfig(
                    name="supplier_products_ftp",
                    type=SupplierProductSourceType.FTP,
                    host="ftp.supplier.example.com",
                    username="supplier_user",
                    password_env_var="SUPPLIER_FTP_PASSWORD",
                    path="supplier_products.csv",
                ),
            ]
        )

        assert len(config.sources) == 3
        assert isinstance(config.sources[0], CSVSourceConfig)
        assert isinstance(config.sources[1], APISourceConfig)
        assert isinstance(config.sources[2], FTPSourceConfig)

    def test_ftp_source_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            FTPSourceConfig(
                name="supplier_products_ftp",
                type=SupplierProductSourceType.FTP,
                host="ftp.supplier.example.com",
                username="supplier_user",
                password_env_var="SUPPLIER_FTP_PASSWORD",
                path="supplier_products.csv",
                password="secret",
            )
