from collections.abc import Sequence

from src.models.supplier_product import SupplierProduct
from src.pipelines.supplier_product.extractors import SupplierProductExtractor
from src.pipelines.supplier_product.loader import LoadResult, SupplierProductLoader
from src.pipelines.supplier_product.transformer import SupplierProductTransformer
from src.pipelines.supplier_product.validator import SupplierProductValidator


class SupplierProductPipelineService:
    """Coordinate the supplier product pipeline lifecycle."""

    def __init__(
        self,
        extractor: SupplierProductExtractor,
        validator: SupplierProductValidator,
        transformer: SupplierProductTransformer,
        loader: SupplierProductLoader,
    ) -> None:
        self._extractor = extractor
        self._validator = validator
        self._transformer = transformer
        self._loader = loader

    async def run(self) -> LoadResult:
        """Execute the Supplier Product pipeline."""

        extracted_records = await self._extractor.extract()
        validated_records = self._validator.validate(extracted_records)

        products: Sequence[SupplierProduct] = self._transformer.transform(
            validated_records
        )

        return self._loader.load(products)
