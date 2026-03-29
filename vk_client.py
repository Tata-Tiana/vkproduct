import requests


class VKClient:
    def __init__(self, access_token, api_version="5.199"):
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = "https://api.vk.com/method"

    def call_method(self, method_name, params=None):
        payload = dict(params or {})
        payload["access_token"] = self.access_token
        payload["v"] = self.api_version

        response = requests.post(
            f"{self.base_url}/{method_name}",
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            error = data["error"]
            message = error.get("error_msg", "Unknown VK API error")
            code = error.get("error_code", "unknown")
            raise RuntimeError(f"VK API error {code}: {message}")

        return data.get("response", {})

    def get_market_categories(self, lang="ru", count=None, offset=None):
        params = {
            "lang": lang,
        }
        if count is not None:
            params["count"] = count
        if offset is not None:
            params["offset"] = offset

        return self.call_method("market.getCategories", params)

    def get_market_upload_server(self, group_id, main_photo=True):
        return self.call_method(
            "photos.getMarketUploadServer",
            {
                "group_id": group_id,
                "main_photo": 1 if main_photo else 0,
            },
        )

    def upload_photo_to_url(self, upload_url, file_path):
        with open(file_path, "rb") as file_handle:
            response = requests.post(
                upload_url,
                files={"file": file_handle},
                timeout=60,
            )
        response.raise_for_status()
        return response.json()

    def save_market_photo(
        self,
        group_id,
        photo,
        server,
        hash_value,
        crop_data=None,
        crop_hash=None,
    ):
        params = {
            "group_id": group_id,
            "photo": photo,
            "server": server,
            "hash": hash_value,
        }
        if crop_data:
            params["crop_data"] = crop_data
        if crop_hash:
            params["crop_hash"] = crop_hash

        return self.call_method("photos.saveMarketPhoto", params)

    def add_market_product(
        self,
        owner_id,
        name,
        description,
        category_id,
        price,
        main_photo_id,
        photo_ids=None,
        old_price=None,
    ):
        params = {
            "owner_id": owner_id,
            "name": name,
            "description": description,
            "category_id": category_id,
            "price": price,
            "main_photo_id": main_photo_id,
        }
        if photo_ids:
            params["photo_ids"] = ",".join(str(photo_id) for photo_id in photo_ids)
        if old_price is not None:
            params["old_price"] = old_price

        return self.call_method("market.add", params)
