from typing import Any
from urllib.parse import quote

from app.core.config import settings
from app.core.time import utcnow
from app.integrations.base import CredentialError, NormalizedLead
from app.integrations.live_base import LiveAdapter


class LiveGoogleSheetsAdapter(LiveAdapter):
    provider = "google_sheets"

    def _spreadsheet_id(self) -> str:
        value = self.credentials.get("spreadsheet_id") or settings.google_sheets_spreadsheet_id
        if not value:
            raise CredentialError("Google Sheets spreadsheet_id is not configured")
        return str(value)

    def _range(self) -> str:
        return str(self.credentials.get("range") or settings.google_sheets_range or "Sheet1!A:Z")

    def _encoded_range(self, range_name: str | None = None) -> str:
        return quote(range_name or self._range(), safe="!: ")

    def _values_url(self, range_name: str | None = None) -> str:
        spreadsheet = quote(self._spreadsheet_id(), safe="")
        return f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet}/values/{self._encoded_range(range_name)}"

    def _read_values(self, range_name: str | None = None) -> list[list[Any]]:
        payload = self._request("GET", self._values_url(range_name))
        values = payload.get("values") or []
        return [list(row) for row in values]

    @staticmethod
    def _normalize_header(value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")

    def _find_row(self, column: str, value: str) -> int | None:
        rows = self._read_values()
        if not rows:
            return None
        headers = [self._normalize_header(item) for item in rows[0]]
        if column not in headers:
            return None
        index = headers.index(column)
        for offset, row in enumerate(rows[1:], start=2):
            cell = row[index] if index < len(row) else ""
            if str(cell) == value:
                return offset
        return None

    def fetch_leads(self, organization_id: str) -> list[NormalizedLead]:
        rows = self._read_values()
        if not rows:
            return []
        headers = [self._normalize_header(item) for item in rows[0]]
        leads: list[NormalizedLead] = []
        for offset, row in enumerate(rows[1:], start=2):
            cells = {key: (row[index] if index < len(row) else "") for index, key in enumerate(headers)}
            email = str(cells.get("email") or "")
            try:
                deal_value = float(str(cells.get("deal_value") or 0).replace(",", "").replace("$", ""))
            except ValueError:
                deal_value = 0.0
            leads.append(
                NormalizedLead(
                    external_id=str(cells.get("external_id") or cells.get("id") or f"sheet-row-{offset}"),
                    name=str(cells.get("name") or email or f"Sheet row {offset}"),
                    email=email or None,
                    company=cells.get("company"),
                    deal_value=deal_value,
                    stage=cells.get("stage"),
                    owner=cells.get("owner"),
                    last_activity_at=self._parse_timestamp(cells.get("last_activity_at")),
                    notes=cells.get("notes"),
                    raw_data={
                        "row": offset,
                        "spreadsheet_id": self._spreadsheet_id(),
                        "range": self._range(),
                        "organization_id": organization_id,
                    },
                )
            )
        return leads

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = str(payload.get("idempotency_key") or "")
        if key:
            existing_row = self._find_row("idempotency_key", key)
            if existing_row:
                return {"reference": f"{self._range().split('!')[0]}!A{existing_row}:G{existing_row}", "status": "created", "idempotent": True}
        values = [
            [
                key,
                str(payload.get("title") or "RevenueOps follow-up"),
                str(payload.get("description") or ""),
                str(payload.get("company") or ""),
                str(payload.get("email") or ""),
                "pending",
                utcnow().isoformat(),
            ]
        ]
        url = f"{self._values_url()}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        result = self._request("POST", url, body={"values": values})
        return {"reference": result.get("updates", {}).get("updatedRange") or "", "status": "created"}

    def update_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_id = str(payload.get("record_id") or payload.get("lead_id") or "")
        row = payload.get("row")
        if not row:
            row = self._find_row("external_id", record_id) if record_id else None
        if not row:
            return self.create_task(payload)
        sheet = self._range().split("!")[0]
        range_name = f"{sheet}!A{row}:G{row}"
        values = [[
            str(payload.get("external_id") or record_id),
            str(payload.get("name") or ""),
            str(payload.get("email") or ""),
            str(payload.get("company") or ""),
            str(payload.get("deal_value") or ""),
            str(payload.get("stage") or ""),
            str(payload.get("notes") or ""),
        ]]
        url = f"{self._values_url(range_name)}?valueInputOption=USER_ENTERED"
        result = self._request("PUT", url, body={"values": values})
        updated = result.get("updatedRange") or range_name
        return {"reference": updated, "status": "updated"}

    def verify_action(self, action_type: str, reference: str) -> bool:
        if not reference:
            return False
        return bool(self._read_values(reference))
