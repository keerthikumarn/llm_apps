"""
Thin wrapper around Amadeus Self-Service APIs (test/sandbox environment).

Handles OAuth2 client-credentials token caching, city/airport code
resolution, flight-offer search, and hotel-offer search. Every public
method returns plain, already-simplified dicts -- callers never see
Amadeus's raw nested response shape, so a schema change on their end
only requires touching the two `_simplify_*` methods here.

"""
import time
from datetime import date, timedelta
import httpx
from app.config import settings


class AmadeusError(Exception):
    """Raised for any Amadeus API failure -- auth, network, or bad response."""


class AmadeusService:
    def __init__(self) -> None:
        self.client = httpx.Client(base_url=settings.amadeus_base_url, timeout=15.0)
        self.token: str | None = None
        self.token_expires_at: float = 0.0

    # ---------- auth ----------
    def get_token(self) -> str | None:
        # Reuse the cached token until close to expiry (30s safety margin)
        # rather than fetching a new one on every single search call.
        if self.token and time.time() < self.token_expires_at - 30:
            return self.token

        if not settings.amadeus_client_id or not settings.amadeus_client_secret:
            raise AmadeusError(
                "Amadeus credentials are not configured. Set AMADEUS_CLIENT_ID "
                "and AMADEUS_CLIENT_SECRET in backend/.env."
            )

        try:
            resp = self.client.post(
                "/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.amadeus_client_id,
                    "client_secret": settings.amadeus_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AmadeusError(f"Amadeus auth failed: {exc}") from exc

        data = resp.json()
        self.token = data["access_token"]
        self.token_expires_at = time.time() + data.get("expires_in", 1800)
        return self.token

    def _get(self, path: str, params: dict) -> dict:
        token = self.get_token()
        try:
            resp = self.client.get(
                path, params=params, headers={"Authorization": f"Bearer {token}"}
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise AmadeusError(
                f"Amadeus API error ({exc.response.status_code}): {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AmadeusError(f"Amadeus request failed: {exc}") from exc
        return resp.json()

    # ---------- location resolution ----------
    def resolve_city_code(self, keyword: str) -> str | None:
        """
        Resolve a free-text place name (e.g. 'Bangalore') to an IATA
        city/airport code (e.g. 'BLR') via Amadeus's own location search --
        deliberately not a hardcoded lookup table, so any city Amadeus
        covers works without a code change here.
        """
        data = self._get(
            "/v1/reference-data/locations",
            {"keyword": keyword, "subType": "CITY,AIRPORT", "page[limit]": 1},
        )
        results = data.get("data", [])
        return results[0]["iataCode"] if results else None

    # ---------- flights ----------dock
    def search_flights(
        self, origin: str, destination: str, departure_date: str, adults: int = 1
    ) -> list[dict]:
        data = self._get(
            "/v2/shopping/flight-offers",
            {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "adults": adults,
                "max": 5,
                "currencyCode": "USD",
            },
        )
        return [self.simplify_flight_offer(o) for o in data.get("data", [])]

    @staticmethod
    def simplify_flight_offer(offer: dict) -> dict:
        itinerary = offer["itineraries"][0]
        first_seg = itinerary["segments"][0]
        last_seg = itinerary["segments"][-1]
        return {
            "id": offer.get("id"),
            "price": offer["price"]["total"],
            "currency": offer["price"]["currency"],
            "carrier": first_seg["carrierCode"],
            "flight_number": f'{first_seg["carrierCode"]}{first_seg["number"]}',
            "departure_airport": first_seg["departure"]["iataCode"],
            "departure_time": first_seg["departure"]["at"],
            "arrival_airport": last_seg["arrival"]["iataCode"],
            "arrival_time": last_seg["arrival"]["at"],
            "duration": itinerary.get("duration"),
            "stops": len(itinerary["segments"]) - 1,
        }

    # ---------- hotels ----------
    def search_hotels(
        self, city_code: str, check_in: str, check_out: str, adults: int = 1
    ) -> list[dict]:
        # Two-step by design: Amadeus's Hotel List API gives hotel IDs for a
        # city, then Hotel Search v3 prices/offers a specific set of IDs.
        hotel_list = self._get(
            "/v1/reference-data/locations/hotels/by-city", {"cityCode": city_code}
        )
        hotel_ids = [h["hotelId"] for h in hotel_list.get("data", [])[:10]]
        if not hotel_ids:
            return []

        offers_data = self._get(
            "/v3/shopping/hotel-offers",
            {
                "hotelIds": ",".join(hotel_ids),
                "adults": adults,
                "checkInDate": check_in,
                "checkOutDate": check_out,
            },
        )
        return [
            self.simplify_hotel_offer(h)
            for h in offers_data.get("data", [])
            if h.get("offers")
        ]

    @staticmethod
    def simplify_hotel_offer(entry: dict) -> dict:
        hotel = entry["hotel"]
        offer = entry["offers"][0]
        return {
            "id": offer.get("id"),
            "hotel_id": hotel.get("hotelId"),
            "name": hotel.get("name"),
            "price": offer["price"]["total"],
            "currency": offer["price"]["currency"],
            "room_description": offer.get("room", {}).get("description", {}).get("text", ""),
            "check_in": offer.get("checkInDate"),
            "check_out": offer.get("checkOutDate"),
        }

    # ---------- helpers ----------
    @staticmethod
    def default_future_date(days: int = 14) -> str:
        return (date.today() + timedelta(days=days)).isoformat()


amadeus_service = AmadeusService()