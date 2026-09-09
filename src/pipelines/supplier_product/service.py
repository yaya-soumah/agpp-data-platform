import polars as pl
from src.pipelines.supplier_product.extractors import SupplierProductExtractor
from src.pipelines.supplier_product.loader import LoadResult, SupplierProductLoader
from src.pipelines.supplier_product.transformer import DefaultSupplierProductTransformer
from src.pipelines.supplier_product.validator import SupplierProductValidator


class SupplierProductPipelineService:
    """Coordinate the supplier product pipeline lifecycle."""

    def __init__(
        self,
        extractor: SupplierProductExtractor,
        validator: SupplierProductValidator,
        transformer: DefaultSupplierProductTransformer,
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

        products: pl.DataFrame = self._transformer.transform(validated_records)

        return self._loader.load(products)
