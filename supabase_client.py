from supabase import create_client

from models import ProductDraftUpdate, SourceRecord


class SupabaseClient:
    def __init__(self, url, service_role_key):
        self.client = create_client(url, service_role_key)

    def get_product_draft_by_id(self, product_id):
        response = (
            self.client.table("vk_products_drafts")
            .select("*")
            .eq("id", product_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def get_product_draft(self, sort_name):
        response = (
            self.client.table("vk_products_drafts")
            .select("*")
            .eq("sort_name", sort_name)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def get_source_by_url(self, product_id, source_url):
        response = (
            self.client.table("vk_product_sources")
            .select("*")
            .eq("product_id", product_id)
            .eq("source_url", source_url)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def get_or_create_product_draft(self, sort_name, product_type="petunia"):
        existing = self.get_product_draft(sort_name)
        if existing:
            return existing

        payload = {
            "sort_name": sort_name,
            "product_type": product_type,
            "status": "draft",
        }

        response = (
            self.client.table("vk_products_drafts")
            .upsert(payload, on_conflict="sort_name")
            .execute()
        )
        rows = response.data or []
        if not rows:
            return self.get_product_draft(sort_name)
        return rows[0]

    def insert_source(
        self,
        product_id,
        source_url,
        source_name,
        source_type,
        source_title,
        parsed_text_raw,
        parsed_characteristics_raw=None,
    ):
        record = SourceRecord(
            product_id=product_id,
            source_url=source_url,
            source_name=source_name,
            source_type=source_type,
            source_title=source_title,
            parsed_text_raw=parsed_text_raw,
            parsed_characteristics_raw=parsed_characteristics_raw,
        )
        payload = record.model_dump(exclude_none=True)
        existing = self.get_source_by_url(product_id, source_url)

        if existing:
            response = (
                self.client.table("vk_product_sources")
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )
        else:
            response = self.client.table("vk_product_sources").insert(payload).execute()

        rows = response.data or []
        return rows[0] if rows else None

    def get_selected_sources(self, product_id):
        response = (
            self.client.table("vk_product_sources")
            .select("*")
            .eq("product_id", product_id)
            .eq("is_selected", True)
            .execute()
        )
        return response.data or []

    def get_all_sources(self, product_id):
        response = (
            self.client.table("vk_product_sources")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )
        return response.data or []

    def update_product_draft(self, product_id, payload):
        if isinstance(payload, ProductDraftUpdate):
            update_payload = payload.model_dump(exclude_none=True)
        else:
            update_payload = payload

        existing = self.get_product_draft_by_id(product_id)
        if existing:
            allowed_keys = set(existing.keys())
            update_payload = {
                key: value
                for key, value in update_payload.items()
                if key in allowed_keys
            }

        response = (
            self.client.table("vk_products_drafts")
            .update(update_payload)
            .eq("id", product_id)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def list_products_by_status(self, status):
        response = (
            self.client.table("vk_products_drafts")
            .select("*")
            .eq("status", status)
            .execute()
        )
        return response.data or []
