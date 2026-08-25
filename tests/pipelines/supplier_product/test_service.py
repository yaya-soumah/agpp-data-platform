from unittest.mock import Mock

from src.models.supplier_product import SupplierProduct
from src.pipelines.supplier_product import (
    LoadResult,
    SupplierProductPipelineService,
    SupplierProductRecord,
    ValidateSupplierProductRecord,
)


def test_pipeline_executes_stages_in_order() -> None:
    extractor = Mock()
    validator = Mock()
    transformer = Mock()
    loader = Mock()

    extracted_records = [
        SupplierProductRecord(
            supplier_product_id="SP-001",
            supplier_id="SUP-001",
            name="Steel Bolt",
        )
    ]

    validated_records = [
        ValidateSupplierProductRecord(
            supplier_product_id="SP-001",
            supplier_id="SUP-001",
            name="Steel Bolt",
        )
    ]

    product = SupplierProduct(
        supplier_product_id="SP-001",
        supplier_id="SUP-001",
        name="Steel Bolt",
    )

    load_result = LoadResult(records_loaded=1)

    extractor.extract.return_value = extracted_records
    validator.validate.return_value = validated_records
    transformer.transform.return_value = [product]
    loader.load.return_value = load_result

    service = SupplierProductPipelineService(
        extractor=extractor,
        validator=validator,
        transformer=transformer,
        loader=loader,
    )

    result = service.run()

    assert result == load_result

    extractor.extract.assert_called_once_with()
    validator.validate.assert_called_once_with(extracted_records)
    transformer.transform.assert_called_once_with(validated_records)
    loader.load.assert_called_once_with([product])
