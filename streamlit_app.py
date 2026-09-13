import os
from datetime import date
from typing import Any

import httpx
import streamlit as st


API_BASE_URL = os.getenv("HEALTHLINK_API_URL", "http://localhost:8001/api/v1").rstrip("/")


class ApiError(Exception):
    pass


def request_json(method: str, path: str, **kwargs) -> Any:
    try:
        response = httpx.request(
            method,
            f"{API_BASE_URL}/{path.lstrip('/')}",
            timeout=120.0,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise ApiError(detail or "The HealthLink service could not process this request.") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise ApiError("Cannot connect to the HealthLink API. Make sure the backend is running.") from exc


@st.cache_data(ttl=15, show_spinner=False)
def get_health() -> dict[str, Any]:
    return request_json("GET", "/health")


@st.cache_data(ttl=300, show_spinner=False)
def get_specialties() -> list[str]:
    return request_json("GET", "/specialties")


@st.cache_data(ttl=60, show_spinner=False)
def get_doctors(specialty: str | None, limit: int) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if specialty:
        params["specialty"] = specialty
    return request_json("GET", "/doctors", params=params)


def show_urgency(level: str) -> None:
    messages = {
        "emergency": (st.error, "Emergency attention may be needed. Contact local emergency services now."),
        "high": (st.warning, "High urgency: seek prompt medical attention."),
        "medium": (st.info, "Moderate urgency: arrange a medical consultation soon."),
        "low": (st.success, "Low urgency based on the provided information."),
    }
    renderer, message = messages.get(level.lower(), (st.info, f"Urgency level: {level.title()}"))
    renderer(message)


def show_assessment(result: dict[str, Any]) -> None:
    symptom_analysis = result.get("symptom_analysis", {})
    recommendations = result.get("doctor_recommendations", {})
    scheduling = result.get("scheduling_options", {})
    summary = result.get("health_summary", {})

    st.markdown("## Your health overview")
    show_urgency(symptom_analysis.get("urgency_level", "unknown"))

    overview, findings = st.columns([1.3, 1], gap="large")
    with overview:
        st.markdown("### Summary")
        st.write(summary.get("summary", "No summary was returned."))
        primary = symptom_analysis.get("primary_complaint")
        if primary:
            st.caption(f"Primary concern: {primary}")
    with findings:
        st.markdown("### Key findings")
        for finding in summary.get("key_findings", []):
            st.markdown(f"- {finding}")
        if not summary.get("key_findings"):
            st.caption("No key findings were returned.")

    st.markdown("### Symptoms identified")
    symptoms = symptom_analysis.get("symptoms", [])
    if symptoms:
        columns = st.columns(min(3, len(symptoms)))
        for index, symptom in enumerate(symptoms):
            with columns[index % len(columns)]:
                with st.container(border=True):
                    st.markdown(f"**{symptom.get('name', 'Symptom').title()}**")
                    st.write(f"Severity: {symptom.get('severity', 'Unknown').title()}")
                    if symptom.get("duration"):
                        st.caption(f"Duration: {symptom['duration']}")
    else:
        st.info("No individual symptoms were returned.")

    st.markdown("### Recommended care team")
    doctors = recommendations.get("recommended_doctors", [])
    if doctors:
        columns = st.columns(min(3, len(doctors)))
        for index, doctor in enumerate(doctors):
            with columns[index % len(columns)]:
                with st.container(border=True):
                    st.markdown(f"#### {doctor.get('name', 'Doctor')}")
                    st.caption(doctor.get("specialty", "Specialty unavailable"))
                    st.metric("Rating", f"{doctor.get('rating', 0):.1f} / 5")
                    st.write(f"{doctor.get('experience_years', 0)} years experience")
                    if doctor.get("location"):
                        st.write(doctor["location"])
        rationale = recommendations.get("specialty_rationale")
        if rationale:
            st.info(rationale)
    else:
        st.info("No doctor recommendations were returned.")

    st.markdown("### Suggested appointment times")
    recommended_slot = scheduling.get("recommended_slot")
    if recommended_slot:
        with st.container(border=True):
            st.markdown("**Best match**")
            st.write(
                f"{recommended_slot.get('doctor_name', 'Doctor')} · "
                f"{recommended_slot.get('date', 'Date unavailable')} at "
                f"{recommended_slot.get('time', 'Time unavailable')}"
            )
            st.caption(f"{recommended_slot.get('duration_minutes', 30)} minute appointment")

    available_slots = scheduling.get("available_slots", [])
    if available_slots:
        with st.expander(f"View all {len(available_slots)} available slots"):
            for slot in available_slots:
                st.write(
                    f"**{slot.get('doctor_name', 'Doctor')}** — "
                    f"{slot.get('date', 'Date unavailable')} at {slot.get('time', 'Time unavailable')}"
                )
    elif not recommended_slot:
        st.info("No scheduling options were returned.")

    actions = summary.get("recommended_actions", [])
    if actions:
        st.markdown("### Recommended next steps")
        for index, action in enumerate(actions, start=1):
            st.markdown(f"{index}. {action}")

    disclaimer = summary.get("disclaimer")
    if disclaimer:
        st.warning(disclaimer)
    st.caption(f"Assessment ID: {result.get('request_id', 'Unavailable')}")


def assessment_page() -> None:
    intro, guidance = st.columns([1.5, 1], gap="large")
    with intro:
        st.markdown("## Tell us what you’re experiencing")
        st.write(
            "Describe your symptoms in your own words. HealthLink will organize the details, "
            "suggest an appropriate care specialty, and surface possible appointment times."
        )
    with guidance:
        with st.container(border=True):
            st.markdown("**Include useful details**")
            st.write("When it started, severity, changes over time, and anything that makes it better or worse.")

    with st.form("assessment_form"):
        concern = st.text_area(
            "Health concern",
            placeholder="Example: I have had a persistent headache and mild fever for three days...",
            height=150,
        )
        left, right = st.columns(2)
        with left:
            user_id = st.text_input("Patient ID (optional)", placeholder="Your reference ID")
            include_date = st.checkbox("I have a preferred appointment date")
            preferred_date = st.date_input(
                "Preferred date",
                value=date.today(),
                disabled=not include_date,
            )
        with right:
            preferred_location = st.text_input(
                "Preferred location (optional)",
                placeholder="City, neighborhood, or clinic",
            )
            st.write("")
            st.caption("Your assessment can take a moment while the care agents review your information.")
        submitted = st.form_submit_button("Start health assessment", type="primary", use_container_width=True)

    if submitted:
        if len(concern.strip()) < 10:
            st.error("Please describe your health concern in at least 10 characters.")
        else:
            payload = {
                "user_input": concern.strip(),
                "user_id": user_id.strip() or None,
                "preferred_date": preferred_date.isoformat() if include_date else None,
                "preferred_location": preferred_location.strip() or None,
            }
            with st.spinner("Reviewing symptoms and finding care options..."):
                try:
                    st.session_state["assessment"] = request_json("POST", "/assess", json=payload)
                except ApiError as exc:
                    st.error(str(exc))

    if st.session_state.get("assessment"):
        st.divider()
        show_assessment(st.session_state["assessment"])


def doctors_page() -> None:
    st.markdown("## Find a doctor")
    st.write("Browse HealthLink’s care network by specialty.")

    try:
        specialties = get_specialties()
    except ApiError as exc:
        st.error(str(exc))
        return

    filters, results = st.columns([1, 2.4], gap="large")
    with filters:
        with st.container(border=True):
            st.markdown("### Filters")
            selected = st.selectbox("Specialty", ["All specialties", *specialties])
            limit = st.slider("Maximum results", min_value=5, max_value=100, value=20, step=5)
            if st.button("Refresh directory", use_container_width=True):
                get_doctors.clear()

    specialty = None if selected == "All specialties" else selected
    try:
        doctors = get_doctors(specialty, limit)
    except ApiError as exc:
        with results:
            st.error(str(exc))
        return

    with results:
        st.caption(f"{len(doctors)} doctors found")
        if not doctors:
            st.info("No doctors match this specialty.")
        for doctor in doctors:
            with st.container(border=True):
                name, rating = st.columns([4, 1])
                with name:
                    st.markdown(f"### {doctor.get('name', 'Doctor')}")
                    st.caption(doctor.get("specialty", "Specialty unavailable"))
                with rating:
                    st.metric("Rating", f"{doctor.get('rating', 0):.1f}")
                details = [
                    f"{doctor.get('experience_years', 0)} years experience",
                    doctor.get("location"),
                    doctor.get("availability"),
                ]
                st.write(" · ".join(str(detail) for detail in details if detail))
                contact = [doctor.get("email"), doctor.get("phone")]
                if any(contact):
                    st.caption(" · ".join(str(item) for item in contact if item))


def about_page() -> None:
    st.markdown("## About HealthLink")
    st.write(
        "HealthLink coordinates symptom analysis, doctor matching, appointment suggestions, "
        "and a concise care summary in one guided workflow."
    )
    st.markdown("### How it works")
    steps = [
        ("1", "Describe", "Share symptoms, duration, and severity."),
        ("2", "Analyze", "AI agents organize symptoms and assess urgency."),
        ("3", "Match", "Relevant doctors and specialties are recommended."),
        ("4", "Plan", "Review appointment options and next steps."),
    ]
    columns = st.columns(4)
    for column, (number, title, detail) in zip(columns, steps):
        with column:
            with st.container(border=True):
                st.caption(f"STEP {number}")
                st.markdown(f"**{title}**")
                st.write(detail)
    st.warning(
        "HealthLink provides informational guidance, not a diagnosis. In an emergency, "
        "contact local emergency services immediately."
    )


st.set_page_config(
    page_title="HealthLink",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --healthlink-navy: #102a43;
        --healthlink-blue: #2563eb;
        --healthlink-mint: #dff7ed;
        --healthlink-surface: #f6f9fc;
    }
    .stApp {
        background: linear-gradient(180deg, #f8fbff 0%, #ffffff 36%);
    }
    [data-testid="stSidebar"] {
        background: var(--healthlink-navy);
    }
    [data-testid="stSidebar"] * {
        color: #f8fafc;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        border-radius: 0.65rem;
        padding: 0.4rem 0.6rem;
    }
    .healthlink-hero {
        padding: 2.2rem 2.4rem;
        border-radius: 1.5rem;
        background: linear-gradient(125deg, #102a43 0%, #164e63 55%, #0f766e 100%);
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 18px 50px rgba(15, 42, 67, 0.16);
    }
    .healthlink-hero h1 {
        margin: 0;
        font-size: clamp(2rem, 5vw, 3.65rem);
        letter-spacing: -0.045em;
        color: white;
    }
    .healthlink-hero p {
        margin: 0.65rem 0 0;
        color: #d9f5ee;
        font-size: 1.08rem;
        max-width: 46rem;
    }
    div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.86);
        border-color: #dbe7f2;
        box-shadow: 0 8px 30px rgba(15, 42, 67, 0.05);
    }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background: var(--healthlink-blue);
        border: 0;
        min-height: 2.8rem;
        font-weight: 700;
    }
    h2, h3 {
        color: var(--healthlink-navy);
        letter-spacing: -0.025em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("# HealthLink")
    st.caption("Smart care navigation")
    page = st.radio("Navigate", ["Assessment", "Doctors", "About"], label_visibility="collapsed")
    st.divider()
    try:
        health = get_health()
        if health.get("status") == "healthy":
            st.success("API connected")
        else:
            st.warning("API status unavailable")
        services = health.get("services", {})
        for service, status in services.items():
            st.caption(f"{service.upper()}: {status}")
    except ApiError:
        st.error("API offline")
        st.caption("Start the FastAPI backend on port 8000.")
    st.divider()
    st.caption("Private by design · Human care first")

st.markdown(
    """
    <section class="healthlink-hero">
        <h1>Care starts with clarity.</h1>
        <p>Understand your symptoms, find the right specialist, and plan your next step with HealthLink.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

if page == "Assessment":
    assessment_page()
elif page == "Doctors":
    doctors_page()
else:
    about_page()
