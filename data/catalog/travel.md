# travel

5 skills. Load a selected skill with `get_skill` before applying it.
Descriptions are the authors' own, unedited -- including the "Do NOT use for" clauses,
which are load-bearing: they are how you tell near-misses apart.
Descriptions: Copyright (c) 2026 Skills IL (Yootech), MIT License. See THIRD_PARTY_NOTICES.md.

## israeli-abroad-trip-planner  `-`
Plans a full trip abroad for Israeli travelers: route, hotels and attractions, anchored by the Israel-specific layer of visa and electronic-authorization rules for an Israeli passport, official Israeli travel warnings, exit restrictions, passport validity and renewal, and travel health and insurance via the kupot. Use when an Israeli is planning or preparing a trip abroad and needs both the itinerary and the Israeli checks. Visa status and travel warnings are always checked live against official sources, never guessed. Do not use for domestic travel in Israel (israeli-travel-planner) or flight price comparison (israeli-flight-finder).

## israeli-flight-compensation  `Sc`
Determines whether an air passenger is owed compensation under Israel's Aviation Services Law (חוק שירותי תעופה, 2012, "חוק טיבי") and drafts a Hebrew demand letter to the airline. Use when a flight to or from Israel was cancelled, delayed, overbooked, downgraded, or moved earlier, and the user asks "am I owed compensation", "pitzuy al bitul tisa", "ta'osa hit'akva", "the airline cancelled my flight", or wants to claim without paying a claim-handling service a cut. Calculates the amount by distance band (2026 figures), explains assistance rights, and routes refusals to small claims. Do NOT use for booking flights (use israeli-flight-finder), lost or damaged baggage (Montreal Convention), travel insurance, or flights with no Israeli departure or arrival.

## israeli-flight-finder  `-`
Compare real flight prices from Ben Gurion (TLV): build pre-filled search links for Google Flights, Skyscanner, and KAYAK for the traveler's exact route and dates, read the live fares off them, and add Israeli-airline baggage for a true total cost. Use when someone asks to find or compare cheap flights from Israel, wants the cheapest fare or the cheapest dates to fly, or asks about El Al, Israir, Arkia, or Wizz Air baggage fees, seasonal TLV pricing, or Issta flight+hotel packages. Presents a real comparison and never quotes invented prices. Do NOT use for domestic travel within Israel (use israeli-travel-planner), train schedules (use railil), or hotel-only bookings.

## israeli-hiking-day-planner  `Sc`
Not a safety clearance, official closures and warnings always override it. Plan a day hike in Israel and get a go, caution or no-go call plus a printable route card. Checks the IMS hourly heat-stress forecast and warnings, flash-flood risk from rain upstream, INPA closed trails and site hours, Home Front Command restrictions, mine areas and IDF firing zones, then works out the latest safe start, a finish before dark and water per person from official INPA and Ministry of Education figures. Use when someone asks if a trail is OK this weekend, plans a hike in the Negev, Judean Desert, Dead Sea, Galilee or Golan, or asks how much water to bring, when to start, or what to do in an emergency on the trail. Do NOT use for general domestic trip planning, accommodation or transport (use israeli-travel-planner), trips abroad, or multi-day treks and camping.

## israeli-travel-planner  `Sc`
Plan domestic travel in Israel with local transportation, accommodations, national parks, and cultural considerations. Use when user asks about traveling in Israel, Israeli hotel chains, bus routes, Israel Railways, Rav-Kav card, national parks, tiyul b'aretz, Dead Sea, Eilat, or trip planning within Israel. Covers Egged/Dan/Kavim buses, train schedules, Rashut HaTeva sites, Shabbat travel restrictions, and seasonal advice.
