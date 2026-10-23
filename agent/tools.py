"""LocalGigs tools with sample gigs and in-memory applications."""

from __future__ import annotations

from strands import tool

GIGS = {
    "G101": {
        "title": "College Event Assistant",
        "location": "Hyderabad",
        "pay": 800,
        "min_age": 18,
        "duration": "1 day",
        "description": "Help organizers with registration and attendee guidance.",
        "organizer_verified": True,
    },
    "G102": {
        "title": "Community Event Helper",
        "location": "Hyderabad",
        "pay": 1000,
        "min_age": 18,
        "duration": "1 day",
        "description": "Help with event setup and attendee coordination.",
        "organizer_verified": True,
    },
    "G103": {
        "title": "Workshop Registration Assistant",
        "location": "Secunderabad",
        "pay": 600,
        "min_age": 18,
        "duration": "1 day",
        "description": "Assist with participant check-in at a skills workshop.",
        "organizer_verified": True,
    },
}

APPLICATIONS: list[dict] = []


@tool
def list_gigs() -> list[dict]:
    """List available local gigs with location, pay, duration and age requirements."""
    return [{"gig_id": gig_id, **gig} for gig_id, gig in GIGS.items()]


@tool
def get_gig(gig_id: str) -> dict:
    """Get the details and eligibility requirements for a specific gig."""
    gig = GIGS.get(gig_id.strip().upper())
    if not gig:
        return {"error": "Gig not found. Use list_gigs to see available gigs."}
    return {"gig_id": gig_id.strip().upper(), **gig}


@tool
def submit_application(
    gig_id: str,
    applicant_name: str,
    age: int,
    availability: str,
    consent: bool,
) -> dict:
    """Submit an application after the applicant explicitly confirms their request."""
    key = gig_id.strip().upper()
    gig = GIGS.get(key)

    if not gig:
        return {"error": "Gig not found."}

    if age < gig["min_age"]:
        return {"error": "You do not meet this gig's minimum age requirement."}

    if not consent:
        return {"error": "Explicit applicant consent is required."}

    if not applicant_name.strip() or not availability.strip():
        return {"error": "Applicant name and availability are required."}

    application = {
        "application_id": f"APP{len(APPLICATIONS) + 1:03d}",
        "gig_id": key,
        "gig_title": gig["title"],
        "applicant_name": applicant_name.strip(),
        "age": age,
        "availability": availability.strip(),
        "status": "submitted",
    }
    APPLICATIONS.append(application)
    return {"success": True, **application}


@tool
def list_applications(applicant_name: str) -> list[dict]:
    """List applications submitted under the supplied applicant name."""
    name = applicant_name.strip().casefold()
    return [
        application.copy()
        for application in APPLICATIONS
        if application["applicant_name"].casefold() == name
    ]


TOOLS = [list_gigs, get_gig, submit_application, list_applications]
