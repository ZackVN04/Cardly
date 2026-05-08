from src.cards.schemas import CardCreate, CardUpdate

# Implementation: Phase 3 — W6 (Huy)
# get_my_card(owner_id: str) -> CardDoc
# create_card(owner_id: str, data: CardCreate) -> CardDoc  # generate slug + QR code
# update_card(owner_id: str, data: CardUpdate) -> CardDoc
# delete_card(owner_id: str) -> None
# get_public_card(slug: str) -> CardDoc  # increments view_count; raises 404 if is_public=False
