"""
LangGraph orchestrator for HealthLink agents (STANDALONE / LEARNING ONLY).

Mirrors core/orchestrator.py as a LangGraph StateGraph so you can see the same
4-step pipeline expressed as nodes + edges. NOT wired into the app — import
build_health_graph() and call .invoke() to experiment.

Flow: symptom -> doctor -> scheduling -> summary -> assemble
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, TypedDict

from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, START, END

from core.llm import LLMClient
from core.schemas import (
    HealthAssessmentRequest,
    HealthAssessmentResponse,
    SymptomExtraction,
    DoctorRecommendation,
    SchedulingRecommendation,
    HealthSummary,
)
from agents.symptom_agent import symptom_agent
from agents.doctor_agent import doctor_agent
from agents.scheduling_agent import scheduling_agent
from agents.summary_agent import summary_agent
from config.settings import Settings, get_settings


logger = logging.getLogger("healthlink.orchestrator_langgraph")


class AssessmentState(TypedDict, total=False):
    """Shared state passed between nodes. Each node reads inputs and writes its output."""
    # Inputs (set at invoke time)
    request: HealthAssessmentRequest
    db_session: Session
    llm_client: Optional[LLMClient]
    settings: Settings
    request_id: str
    # Per-step outputs (each node fills one)
    symptom_analysis: SymptomExtraction
    doctor_recommendation: DoctorRecommendation
    scheduling_recommendation: SchedulingRecommendation
    health_summary: HealthSummary
    response: HealthAssessmentResponse


def _symptom_node(state: AssessmentState) -> dict:
    result = symptom_agent(
        user_input=state["request"].user_input,
        llm_client=state.get("llm_client"),
        settings=state["settings"],
        use_rag=True,
    )
    return {"symptom_analysis": result}


def _doctor_node(state: AssessmentState) -> dict:
    result = doctor_agent(
        symptom_analysis=state["symptom_analysis"],
        db_session=state["db_session"],
        llm_client=state.get("llm_client"),
        settings=state["settings"],
        max_recommendations=3,
    )
    return {"doctor_recommendation": result}


def _scheduling_node(state: AssessmentState) -> dict:
    result = scheduling_agent(
        doctor_recommendation=state["doctor_recommendation"],
        urgency_level=state["symptom_analysis"].urgency_level,
        llm_client=state.get("llm_client"),
        settings=state["settings"],
        preferred_date=state["request"].preferred_date,
    )
    return {"scheduling_recommendation": result}


def _summary_node(state: AssessmentState) -> dict:
    result = summary_agent(
        symptom_analysis=state["symptom_analysis"],
        doctor_recommendation=state["doctor_recommendation"],
        scheduling_recommendation=state["scheduling_recommendation"],
        llm_client=state.get("llm_client"),
        settings=state["settings"],
    )
    return {"health_summary": result}


def _assemble_node(state: AssessmentState) -> dict:
    request = state["request"]
    response = HealthAssessmentResponse(
        request_id=state["request_id"],
        timestamp=datetime.utcnow(),
        symptom_analysis=state["symptom_analysis"],
        doctor_recommendations=state["doctor_recommendation"],
        scheduling_options=state["scheduling_recommendation"],
        health_summary=state["health_summary"],
        metadata={
            "user_id": request.user_id,
            "preferred_location": request.preferred_location,
            "processing_time_ms": 0,
        },
    )
    return {"response": response}


def build_health_graph():
    """Build and compile the linear agent pipeline as a LangGraph graph."""
    graph = StateGraph(AssessmentState)
    graph.add_node("symptom", _symptom_node)
    graph.add_node("doctor", _doctor_node)
    graph.add_node("scheduling", _scheduling_node)
    graph.add_node("summary", _summary_node)
    graph.add_node("assemble", _assemble_node)

    graph.add_edge(START, "symptom")
    graph.add_edge("symptom", "doctor")
    graph.add_edge("doctor", "scheduling")
    graph.add_edge("scheduling", "summary")
    graph.add_edge("summary", "assemble")
    graph.add_edge("assemble", END)

    return graph.compile()


def orchestrate_with_langgraph(
    request: HealthAssessmentRequest,
    db_session: Session,
    llm_client: Optional[LLMClient] = None,
    settings: Optional[Settings] = None,
) -> HealthAssessmentResponse:
    """Same signature/result as orchestrate_health_assessment, run via LangGraph."""
    settings = settings or get_settings()
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] Running LangGraph orchestration")

    final_state = build_health_graph().invoke({
        "request": request,
        "db_session": db_session,
        "llm_client": llm_client,
        "settings": settings,
        "request_id": request_id,
    })
    return final_state["response"]


if __name__ == "__main__":
    # Wiring check: compiles the graph and prints node order. No LLM/DB needed.
    compiled = build_health_graph()
    nodes = compiled.get_graph().nodes
    print("Compiled LangGraph nodes:", list(nodes))
    assert {"symptom", "doctor", "scheduling", "summary", "assemble"} <= set(nodes)
    print("Graph wiring OK")
