"""CSV import (GR-31): a preview with each row's problems, then the same file saved.

**The header row** (any order, any case; ``name`` and ``price`` are required, other columns are
ignored and listed in the preview)::

    name, description, sku, variant, option1_name, option1_value, option2_name, option2_value,
    option3_name, option3_value, price, currency, stock, url, image_url, active

- One line is one product, or one variant of a product. Lines with the same ``name`` (ignoring
  case) are one product; a line with a ``variant`` (or option values) is a variant of it, priced
  by its own ``price``. A variant with no name is called by its option values ("Blue / M").
- ``price`` is a plain number ("799" or "799.50", thousands commas allowed); ``currency`` is an
  ISO 4217 code and defaults to the workspace's; ``stock`` is a whole number, blank when not
  recorded; ``active`` is yes/no (blank: yes); ``url`` and ``image_url`` start with https://.
- **Upsert.** A line is matched by ``sku`` first (a product's or a variant's), else by the
  product's ``name`` and the ``variant`` name. A match is updated, anything else is created. A
  blank cell never clears a value on an update, and variants the file doesn't mention stay.
- **Errors.** A line with a problem is listed with the reason and left out; the rest is saved.
  Nothing is saved at all if the file is over the plan's rows (``catalogue_import_rows``). New
  products stop at the plan's ``catalogue_products``.
- The file is read again when it is saved, so the preview can't go stale. Text, not a form:
  the API's body limit makes ~900,000 characters the ceiling.

Pure parsing (``parse``) is separate from the database work (``plan`` and ``apply``).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import check_entitlement, quota_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError
from socialhood.models.catalogue import Product, ProductSource, ProductVariant
from socialhood.repositories import catalogue as repo
from socialhood.schemas.catalogue import ImportPreview, ImportResult, ImportRowOut
from socialhood.services.catalogue import money, products
from socialhood.services.catalogue.products import ProductData, VariantData

COLUMNS = (
    "name",
    "description",
    "sku",
    "variant",
    "option1_name",
    "option1_value",
    "option2_name",
    "option2_value",
    "option3_name",
    "option3_value",
    "price",
    "currency",
    "stock",
    "url",
    "image_url",
    "active",
)
REQUIRED = ("name", "price")
BOM = chr(0xFEFF)  # Excel puts one at the start of a UTF-8 file
MAX_SHOWN = 500  # rows listed in a preview (the counts cover them all)
YES = {"yes", "y", "true", "1"}
NO = {"no", "n", "false", "0"}

COPY = {
    "empty": "The file has no rows.",
    "no_header": "The first line must be the header row, with at least name and price.",
    "missing_column": "The header row has no {column} column.",
    "name": "Add the product's name (up to 200 characters).",
    "price": "Enter a price, like 799 or 799.50.",
    "stock": "Stock must be a whole number, or blank when you don't track it.",
    "active": "Use yes or no.",
    "option_half": "Give each option both a name and a value.",
    "variant_title": "A variant's name can have up to 120 characters.",
    "variant_twice": "Another line has the same variant of this product.",
    "sku_twice": "Another line has the same SKU.",
    "sku_long": "A SKU can have up to 80 characters.",
    "sku_two_products": "These lines' SKUs belong to different products.",
    "sku_of_variant": "This SKU belongs to a variant of a product. Add the variant's name.",
    "no_variant": "This product has variants, so this line needs a variant name.",
    "plain_twice": "This product appears twice without a variant. Add a variant name.",
    "currency_mixed": "This product's lines use different currencies.",
    "currency_saved": (
        "This product is saved in {currency}. Change its currency in the product first."
    ),
    "plan": "Your plan includes {limit:,} products.",
}


@dataclass
class Row:
    line: int
    name: str = ""
    description: str | None = None
    sku: str | None = None
    variant: str | None = None
    options: dict[str, str] = field(default_factory=dict)
    price_text: str = ""
    price_minor: int | None = None
    currency: str | None = None  # as written in the file; the group settles the rest
    stock: int | None = None
    url: str | None = None
    image_url: str | None = None
    active: bool | None = None
    errors: list[str] = field(default_factory=list)
    action: str = "create"


@dataclass
class Parsed:
    rows: list[Row]
    columns: list[str]  # the recognised header columns
    ignored: list[str]


def _delimiter(first_line: str) -> str:
    counts = {d: first_line.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] else ","


def _cell(raw: dict[str, str], key: str) -> str:
    return (raw.get(key) or "").strip()


def parse(text: str) -> Parsed:
    """Read the file into rows with their own problems. Raises ApiError for a file that isn't a
    catalogue at all (no rows, no header)."""
    text = text.removeprefix(BOM)
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise products.invalid("csv", COPY["no_header"])
    reader = csv.DictReader(io.StringIO(text), delimiter=_delimiter(lines[0]))
    header = [h.strip().casefold() for h in (reader.fieldnames or [])]
    for column in REQUIRED:
        if column not in header:
            raise products.invalid("csv", COPY["missing_column"].format(column=column))
    reader.fieldnames = header
    rows: list[Row] = []
    for raw in reader:
        raw = {k: v for k, v in raw.items() if k is not None and isinstance(v, str)}
        if not any(v.strip() for v in raw.values()):
            continue  # a blank line
        rows.append(_row(raw, reader.line_num))
    if not rows:
        raise products.invalid("csv", COPY["empty"])
    return Parsed(
        rows=rows,
        columns=[c for c in header if c in COLUMNS],
        ignored=[c for c in header if c and c not in COLUMNS],
    )


def _row(raw: dict[str, str], line: int) -> Row:
    row = Row(line=line)
    name = _cell(raw, "name")
    if not name or len(name) > 200:
        row.errors.append(COPY["name"])
    row.name = name[:200]
    row.description = products.clean_text(_cell(raw, "description")[:2000])
    sku = _cell(raw, "sku")
    if len(sku) > 80:
        row.errors.append(COPY["sku_long"])
        sku = ""
    row.sku = sku or None
    variant = _cell(raw, "variant")
    for n in (1, 2, 3):
        key, value = _cell(raw, f"option{n}_name"), _cell(raw, f"option{n}_value")
        if key and value:
            row.options[key[:40]] = value[:80]
        elif key or value:
            row.errors.append(COPY["option_half"])
    if not variant and row.options:
        variant = " / ".join(row.options.values())
    if len(variant) > 120:
        row.errors.append(COPY["variant_title"])
        variant = variant[:120]
    row.variant = variant or None
    currency = _cell(raw, "currency").upper()
    if currency and not money.valid_currency(currency):
        row.errors.append(products.COPY["currency"])
        currency = ""
    row.currency = currency or None
    row.price_text = _cell(raw, "price")
    if not row.price_text:
        row.errors.append(COPY["price"])
    stock = _cell(raw, "stock")
    if stock:
        if stock.isdigit() and int(stock) <= 10_000_000:
            row.stock = int(stock)
        else:
            row.errors.append(COPY["stock"])
    active = _cell(raw, "active").casefold()
    if active in YES:
        row.active = True
    elif active in NO:
        row.active = False
    elif active:
        row.errors.append(COPY["active"])
    for key, attr in (("url", "url"), ("image_url", "image_url")):
        value = _cell(raw, key)
        if value:
            try:
                setattr(row, attr, products.https_url(value, key))
            except ApiError as error:
                row.errors.append(error.errors[0].message)
    return row


# ---------------------------------------------------------------- matching existing products


@dataclass
class Group:
    key: str
    rows: list[Row]
    product: Product | None = None
    existing: list[ProductVariant] = field(default_factory=list)

    @property
    def valid(self) -> list[Row]:
        return [r for r in self.rows if not r.errors]


@dataclass
class Plan:
    parsed: Parsed
    groups: list[Group]
    row_cap: int


def _group(rows: list[Row]) -> list[Group]:
    groups: dict[str, Group] = {}
    for row in rows:
        key = row.name.casefold()
        groups.setdefault(key, Group(key, [])).rows.append(row)
    return list(groups.values())


def _check_group_shape(group: Group) -> None:
    """Rows of one product that can't all be true together."""
    named = [r for r in group.rows if r.name]
    with_variant = [r for r in named if r.variant]
    plain = [r for r in named if not r.variant]
    if with_variant:
        for row in plain:
            row.errors.append(COPY["no_variant"])
    elif len(plain) > 1:
        for row in plain[1:]:
            row.errors.append(COPY["plain_twice"])
    seen_titles: set[str] = set()
    for row in with_variant:
        title = (row.variant or "").casefold()
        if title in seen_titles:
            row.errors.append(COPY["variant_twice"])
        seen_titles.add(title)


def _check_file_skus(rows: list[Row]) -> None:
    seen: set[str] = set()
    for row in rows:
        if row.sku is None:
            continue
        if row.sku in seen:
            row.errors.append(COPY["sku_twice"])
        seen.add(row.sku)


async def plan(session: AsyncSession, text: str) -> Plan:
    """Read, check and match the file against the catalogue. Needs the catalogue on the plan and
    the file within the plan's rows."""
    await check_entitlement(session, products.KEY)
    row_cap = int(entitlement(await current_plan(session), "catalogue_import_rows"))
    parsed = parse(text)
    if len(parsed.rows) > row_cap:
        raise quota_error(
            "catalogue_import_rows",
            row_cap,
            f"This file has {len(parsed.rows):,} rows. Your plan includes {row_cap:,} rows in one "
            "import.",
        )
    _check_file_skus(parsed.rows)
    groups = _group(parsed.rows)
    for group in groups:
        _check_group_shape(group)
    await _match(session, groups)
    _settle_prices(groups, await products.default_currency(session))
    await _enforce_product_cap(session, groups)
    return Plan(parsed, groups, row_cap)


async def _match(session: AsyncSession, groups: list[Group]) -> None:
    skus = sorted({r.sku for g in groups for r in g.rows if r.sku})
    by_sku = await repo.by_sku(session, skus)
    by_name = await repo.by_names(session, [g.rows[0].name for g in groups if g.rows[0].name])
    owners: dict[str, Product | None] = {}
    for group in groups:
        found = {by_sku[r.sku].id: by_sku[r.sku] for r in group.rows if r.sku and r.sku in by_sku}
        if len(found) > 1:
            for row in group.rows:
                row.errors.append(COPY["sku_two_products"])
            owners[group.key] = None
            continue
        product = next(iter(found.values()), None) or by_name.get(group.key)
        owners[group.key] = product
    taken: dict[object, str] = {}
    for group in groups:  # two groups can't both update one product
        product = owners[group.key]
        if product is None:
            continue
        if product.id in taken:
            for row in group.rows:
                row.errors.append(COPY["sku_two_products"])
            continue
        taken[product.id] = group.key
        group.product = product
    present = await repo.variants_of(session, [g.product.id for g in groups if g.product])
    for group in groups:
        if group.product is None:
            continue
        group.existing = present.get(group.product.id, [])
        for row in group.rows:
            row.action = "update" if _variant_of(group, row) or not row.variant else "create"
            if row.sku and not row.variant and any(v.sku == row.sku for v in group.existing):
                row.errors.append(COPY["sku_of_variant"])  # a variant's SKU on a plain line


def _variant_of(group: Group, row: Row) -> ProductVariant | None:
    if not row.variant:
        return None
    if row.sku:
        for variant in group.existing:
            if variant.sku == row.sku:
                return variant
    title = row.variant.casefold()
    return next((v for v in group.existing if v.title.casefold() == title), None)


def _settle_prices(groups: list[Group], default: str) -> None:
    """A product's currency is what its lines say, else what it is saved in, else the workspace's;
    then each line's price is read in it."""
    for group in groups:
        given = {r.currency for r in group.rows if r.currency}
        saved = group.product.currency if group.product is not None else None
        if len(given) > 1:
            for row in group.rows:
                if row.currency != next(iter(sorted(given))):
                    row.errors.append(COPY["currency_mixed"])
        currency = (sorted(given)[0] if given else None) or saved or default
        if saved is not None and given and currency != saved:
            for row in group.rows:
                row.errors.append(COPY["currency_saved"].format(currency=saved))
        for row in group.rows:
            row.currency = currency
            if not row.price_text:
                continue
            try:
                row.price_minor = money.parse(row.price_text, currency)
            except ValueError as error:
                row.errors.append(str(error))


async def _enforce_product_cap(session: AsyncSession, groups: list[Group]) -> None:
    cap = int(entitlement(await current_plan(session), "catalogue_products"))
    room = max(cap - await repo.count_products(session), 0)
    for group in groups:
        if group.product is not None or not group.valid:
            continue
        if room <= 0:
            for row in group.valid:
                row.errors.append(COPY["plan"].format(limit=cap))
        else:
            room -= 1


# ---------------------------------------------------------------- the preview and the save


def preview(planned: Plan) -> ImportPreview:
    rows = sorted((r for g in planned.groups for r in g.rows), key=lambda r: r.line)
    valid = [r for r in rows if not r.errors]
    shown = [
        ImportRowOut(
            line=r.line,
            action="error" if r.errors else r.action,
            name=r.name,
            variant=r.variant,
            errors=r.errors,
        )
        for r in rows[:MAX_SHOWN]
    ]
    return ImportPreview(
        rows=shown,
        total_rows=len(rows),
        create=sum(1 for r in valid if r.action == "create"),
        update=sum(1 for r in valid if r.action == "update"),
        errors=len(rows) - len(valid),
        products=sum(1 for g in planned.groups if g.valid),
        row_cap=planned.row_cap,
        columns=list(COLUMNS),
        ignored_columns=planned.parsed.ignored,
    )


async def apply(session: AsyncSession, planned: Plan) -> ImportResult:
    """Save every valid row; the caller commits."""
    created = updated = skipped = touched = 0
    for group in planned.groups:
        valid = group.valid
        skipped += len(group.rows) - len(valid)
        if not valid:
            continue
        await _apply_group(session, group, valid)
        created += sum(1 for r in valid if r.action == "create")
        updated += sum(1 for r in valid if r.action == "update")
        touched += 1
    return ImportResult(created=created, updated=updated, skipped=skipped, products=touched)


async def _apply_group(session: AsyncSession, group: Group, valid: list[Row]) -> None:
    first = valid[0]
    product = group.product
    if product is None:
        data = ProductData(name=first.name, currency=first.currency or money.DEFAULT_CURRENCY)
    else:
        data = products.data_of(product, group.existing)
        data.name = first.name
    for row in valid:  # blank cells never clear a value
        if row.description is not None:
            data.description = row.description
        if row.url is not None:
            data.url = row.url
        if row.image_url is not None:
            data.image_url = row.image_url
        if row.active is not None:
            data.active = row.active
    for row in valid:
        if row.variant:
            _merge_variant(group, data, row)
        else:
            data.price_minor = row.price_minor
            if row.sku:
                data.sku = row.sku
            if row.stock is not None:
                data.stock = row.stock
    source = ProductSource(product.source) if product is not None else ProductSource.CSV
    await products.save(session, data, source=source, product=product)


def _merge_variant(group: Group, data: ProductData, row: Row) -> None:
    assert row.variant is not None
    assert row.price_minor is not None
    match = _variant_of(group, row)
    wanted = VariantData(
        title=row.variant,
        price_minor=row.price_minor,
        options=row.options,
        sku=row.sku,
        stock=row.stock,
        id=match.id if match else None,
    )
    if match is not None:
        for index, current in enumerate(data.variants):
            if current.id == match.id:
                wanted.sku = row.sku or current.sku
                wanted.stock = row.stock if row.stock is not None else current.stock
                wanted.options = row.options or current.options
                wanted.external_id = current.external_id
                data.variants[index] = wanted
                return
    data.variants.append(wanted)
