"""
AiGo Backend - LangGraph Smart Re-plan Workflow
Handles dynamic itinerary adjustments based on real-time triggers
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal, TypedDict
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domains.itinerary.schemas import (
    ReplanChange,
    ReplanSummary,
    ReplanTriggerType,
    ReplanReason,
    GPSLocation,
)
from app.domains.itinerary.tools import (
    GoogleMapsTransitTool,
    TravelpayoutsTool,
    WeatherTool,
)

logger = logging.getLogger(__name__)


# ============ Replan State Definition ============


class ReplanStep(str, Enum):
    """Steps in the replan workflow."""

    LOADING_STATE = "loading_state"
    IMPACT_ANALYSIS = "impact_analysis"
    DYNAMIC_SUBSTITUTION = "dynamic_substitution"
    TRANSIT_UPDATE = "transit_update"
    MONETIZATION_UPDATE = "monetization_update"
    FINALIZATION = "finalization"
    ERROR = "error"


class ImpactedActivity(BaseModel):
    """An activity that is impacted by the trigger."""

    activity_id: str
    day_number: int
    activity_index: int
    title: str
    category: str
    start_time: str | None
    end_time: str | None
    location: dict | None
    impact_reason: str
    impact_level: str  # minor, moderate, major
    is_outdoor: bool
    requires_substitution: bool


class SubstitutionSuggestion(BaseModel):
    """A suggested substitution for an impacted activity."""

    original_activity_id: str
    new_activity: dict
    reason: str
    confidence_score: float
    transit_details: dict | None = None
    affiliate_url: str | None = None


class ReplanState(TypedDict):
    """
    State for the LangGraph replan workflow.
    
    Tracks all data through the smart replan process.
    """

    # Input
    itinerary_id: str
    user_id: str | None
    
    # Trigger info
    trigger_type: str  # weather, traffic, crowd, user_request
    trigger_reason: str  # user_initiated, system_proactive
    trigger_details: str | None
    current_location: dict | None  # GPSLocation as dict
    affected_day: int | None
    affected_activity_ids: list[str] | None
    user_preferences: dict | None

    # Current itinerary state
    current_data: dict  # The existing AIFullItinerary data
    current_version: int

    # Messages for LLM
    messages: Annotated[list[BaseMessage], add_messages]

    # Current step
    current_step: ReplanStep
    step_progress: int
    step_message: str

    # Impact analysis results
    impacted_activities: list[ImpactedActivity]
    weather_data: dict | None
    traffic_data: dict | None
    crowd_data: dict | None

    # Substitution results
    substitutions: list[SubstitutionSuggestion]

    # Changes tracking
    changes: list[ReplanChange]
    summary: ReplanSummary | None

    # Final output
    updated_data: dict | None
    new_version: int

    # Error handling
    error: str | None
    is_critical: bool
    alert_message: str | None

    # Progress callback
    progress_callback: Any | None


# ============ LLM Configuration ============


def get_llm(temperature: float = 0.5) -> ChatOpenAI:
    """Get configured ChatOpenAI instance for replan."""
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
    )


# ============ Prompts ============


IMPACT_ANALYSIS_PROMPT = """You are an expert travel planner analyzing the impact of a real-time trigger on a travel itinerary.

Trigger Type: {trigger_type}
Trigger Details: {trigger_details}
Affected Day: {affected_day}

Current Weather Data:
{weather_data}

Current Itinerary for Analysis:
{itinerary_snippet}

User's Current Location (if available):
{current_location}

Analyze which activities are impacted by this trigger and determine:
1. Which specific activities need to be changed
2. The impact level (minor, moderate, major)
3. Whether the activity is outdoor (affected by weather)
4. Whether it requires a full substitution or just rescheduling

Return a JSON array of impacted activities with:
- activity_id: The activity identifier
- day_number: Day number in the itinerary
- activity_index: Index within that day
- title: Activity title
- impact_reason: Why this activity is impacted
- impact_level: "minor", "moderate", or "major"
- is_outdoor: true/false
- requires_substitution: true if needs replacement, false if just reschedule

Only return activities that are ACTUALLY impacted. Be specific about the reasoning.
Return ONLY valid JSON array, no markdown."""


SUBSTITUTION_PROMPT = """You are an expert travel planner finding alternative activities.

Original Activity:
{original_activity}

Trigger: {trigger_type} - {trigger_details}
Impact Reason: {impact_reason}

Destination: {destination}
User Preferences: {preferences}
Time Slot: {time_slot}
Budget Range: {budget_range}

Weather Conditions:
{weather_conditions}

Available Nearby Alternatives (from Google Places):
{nearby_alternatives}

Find the best substitute activity that:
1. Matches the original activity's purpose/category
2. Is appropriate given the trigger (e.g., indoor if raining)
3. Fits the same time slot and budget
4. Is nearby to minimize travel disruption
5. Provides a great experience

Return JSON with:
- title: Name of the replacement activity
- description: Brief description
- category: Activity category
- location: {{name, address, latitude, longitude, place_id}}
- start_time: Suggested start time (HH:MM)
- end_time: Suggested end time (HH:MM)
- duration_minutes: Duration
- estimated_cost: Cost estimate
- reason: Why this is a good substitute
- confidence_score: 0.0-1.0 confidence in this suggestion

Return ONLY valid JSON, no markdown."""


# ============ Node Functions ============


async def load_state_node(state: ReplanState) -> dict:
    """
    Load the existing itinerary state for modification.
    
    Uses LangGraph checkpointer to restore previous state if available.
    """
    logger.info(f"Loading state for itinerary {state['itinerary_id']}")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=ReplanStep.LOADING_STATE,
            progress=5,
            message="📂 Loading your current itinerary...",
        )

    # Validate we have the current data
    if not state.get("current_data"):
        return {
            "error": "No current itinerary data available",
            "current_step": ReplanStep.ERROR,
        }

    return {
        "current_step": ReplanStep.IMPACT_ANALYSIS,
        "step_progress": 10,
        "step_message": "Analyzing impact of changes...",
    }


async def impact_analysis_node(state: ReplanState) -> dict:
    """
    Analyze which activities are impacted by the trigger.
    
    Instead of regenerating the full plan, identifies specific affected activities.
    """
    logger.info(f"Analyzing impact for trigger: {state['trigger_type']}")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=ReplanStep.IMPACT_ANALYSIS,
            progress=20,
            message="🔍 Analyzing which activities are affected...",
        )

    current_data = state["current_data"]
    trigger_type = state["trigger_type"]
    trigger_details = state.get("trigger_details", "")
    affected_day = state.get("affected_day")

    # Gather real-time data based on trigger type
    weather_data = None
    traffic_data = None
    crowd_data = None

    try:
        if trigger_type == "weather":
            weather_data = await _fetch_weather_data(current_data)
        elif trigger_type == "traffic":
            traffic_data = await _fetch_traffic_data(current_data, state.get("current_location"))
        elif trigger_type == "crowd":
            crowd_data = await _fetch_crowd_data(current_data)
    except Exception as e:
        logger.warning(f"Failed to fetch real-time data: {e}")

    # Determine which days to analyze
    daily_plans = current_data.get("daily_plans", [])
    days_to_analyze = []
    
    if affected_day:
        days_to_analyze = [p for p in daily_plans if p.get("day_number") == affected_day]
    else:
        # Analyze today and tomorrow only
        today = date.today()
        for plan in daily_plans:
            plan_date = plan.get("date")
            if plan_date:
                if isinstance(plan_date, str):
                    plan_date = date.fromisoformat(plan_date)
                if plan_date >= today and plan_date <= today + timedelta(days=2):
                    days_to_analyze.append(plan)

    if not days_to_analyze:
        days_to_analyze = daily_plans[:2]  # Default to first 2 days

    # Use LLM to analyze impact
    llm = get_llm(temperature=0.3)
    prompt = ChatPromptTemplate.from_template(IMPACT_ANALYSIS_PROMPT)

    itinerary_snippet = _format_days_for_analysis(days_to_analyze)
    
    messages = prompt.format_messages(
        trigger_type=trigger_type,
        trigger_details=trigger_details,
        affected_day=affected_day or "Not specified",
        weather_data=str(weather_data) if weather_data else "Not available",
        itinerary_snippet=itinerary_snippet,
        current_location=str(state.get("current_location")) if state.get("current_location") else "Not available",
    )

    try:
        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        impacted_list = json.loads(content)
        
        impacted_activities = [
            ImpactedActivity(**item) for item in impacted_list
        ]

        # Determine if this is critical
        is_critical = any(
            a.impact_level == "major" and a.requires_substitution
            for a in impacted_activities
        )
        
        alert_message = None
        if is_critical and trigger_type == "weather":
            alert_message = f"⚠️ Weather Alert: {trigger_details or 'Bad weather detected'}. {len(impacted_activities)} activities affected!"
        elif is_critical and trigger_type == "traffic":
            alert_message = f"🚗 Traffic Alert: Heavy traffic detected. Consider alternative routes!"
        elif is_critical and trigger_type == "crowd":
            alert_message = f"👥 Crowd Alert: Some venues are very crowded. We found alternatives!"

        logger.info(f"Found {len(impacted_activities)} impacted activities")

        return {
            "impacted_activities": impacted_activities,
            "weather_data": weather_data,
            "traffic_data": traffic_data,
            "crowd_data": crowd_data,
            "is_critical": is_critical,
            "alert_message": alert_message,
            "current_step": ReplanStep.DYNAMIC_SUBSTITUTION,
            "step_progress": 35,
            "step_message": f"Found {len(impacted_activities)} activities to adjust...",
        }

    except Exception as e:
        logger.error(f"Impact analysis failed: {e}")
        return {
            "error": f"Failed to analyze impact: {str(e)}",
            "current_step": ReplanStep.ERROR,
        }


async def dynamic_substitution_node(state: ReplanState) -> dict:
    """
    Find substitutions for impacted activities based on trigger type.
    
    Weather: Swap outdoor with indoor
    Traffic: Adjust transit or add pit-stops
    Crowd: Find hidden gems or reschedule
    """
    logger.info("Finding substitutions for impacted activities")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=ReplanStep.DYNAMIC_SUBSTITUTION,
            progress=45,
            message="🔄 Finding alternative activities...",
        )

    impacted = state.get("impacted_activities", [])
    trigger_type = state["trigger_type"]
    current_data = state["current_data"]
    
    if not impacted:
        return {
            "substitutions": [],
            "current_step": ReplanStep.TRANSIT_UPDATE,
            "step_progress": 60,
            "step_message": "No substitutions needed",
        }

    substitutions = []
    changes = []

    for activity in impacted:
        if not activity.requires_substitution:
            # Just reschedule - add as a change but no substitution
            changes.append(ReplanChange(
                change_type="rescheduled",
                day_number=activity.day_number,
                original_item={"id": activity.activity_id, "title": activity.title},
                new_item=None,
                reason=activity.impact_reason,
                transit_updated=False,
                affiliate_links_updated=False,
            ))
            continue

        try:
            # Get the original activity data
            original = _get_activity_from_data(
                current_data, 
                activity.day_number, 
                activity.activity_index
            )
            
            if not original:
                continue

            # Find substitution based on trigger type
            if trigger_type == "weather":
                sub = await _find_weather_substitution(
                    original, activity, state
                )
            elif trigger_type == "traffic":
                sub = await _find_traffic_substitution(
                    original, activity, state
                )
            elif trigger_type == "crowd":
                sub = await _find_crowd_substitution(
                    original, activity, state
                )
            else:  # user_request
                sub = await _find_general_substitution(
                    original, activity, state
                )

            if sub:
                substitutions.append(sub)
                changes.append(ReplanChange(
                    change_type="substitution",
                    day_number=activity.day_number,
                    original_item=original,
                    new_item=sub.new_activity,
                    reason=sub.reason,
                    transit_updated=False,
                    affiliate_links_updated=False,
                ))

        except Exception as e:
            logger.warning(f"Failed to find substitution for {activity.title}: {e}")

    return {
        "substitutions": substitutions,
        "changes": changes,
        "current_step": ReplanStep.TRANSIT_UPDATE,
        "step_progress": 60,
        "step_message": f"Found {len(substitutions)} alternatives",
    }


async def _find_weather_substitution(
    original: dict,
    activity: ImpactedActivity,
    state: ReplanState,
) -> SubstitutionSuggestion | None:
    """Find indoor alternative for weather-affected outdoor activity."""
    current_data = state["current_data"]
    destination = current_data.get("destination_city", current_data.get("destination", ""))
    
    # Search for nearby indoor alternatives
    try:
        place_tool = GoogleMapsTransitTool.place_search
        
        # Search for indoor alternatives
        category = original.get("category", "sightseeing")
        indoor_queries = {
            "sightseeing": f"indoor attractions museums galleries in {destination}",
            "dining": f"indoor restaurants cafes in {destination}",
            "entertainment": f"indoor entertainment shopping mall in {destination}",
            "shopping": f"shopping mall department store in {destination}",
        }
        
        query = indoor_queries.get(category.lower(), f"indoor activities in {destination}")
        
        # Get location for nearby search
        loc = original.get("location", {})
        
        results = await place_tool._arun(query=query, radius=3000)
        
        if not results:
            return None

        # Use LLM to select best alternative
        llm = get_llm(temperature=0.5)
        prompt = ChatPromptTemplate.from_template(SUBSTITUTION_PROMPT)
        
        messages = prompt.format_messages(
            original_activity=str(original),
            trigger_type="weather",
            trigger_details=state.get("trigger_details", "Rain expected"),
            impact_reason=activity.impact_reason,
            destination=destination,
            preferences=str(state.get("user_preferences", {})),
            time_slot=f"{original.get('start_time', '10:00')} - {original.get('end_time', '12:00')}",
            budget_range=str(original.get("estimated_cost", "moderate")),
            weather_conditions=str(state.get("weather_data", {})),
            nearby_alternatives=str(results[:5]),
        )

        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        new_activity = json.loads(content)

        return SubstitutionSuggestion(
            original_activity_id=activity.activity_id,
            new_activity=new_activity,
            reason=f"Indoor alternative due to weather: {activity.impact_reason}",
            confidence_score=new_activity.get("confidence_score", 0.8),
        )

    except Exception as e:
        logger.error(f"Weather substitution failed: {e}")
        return None


async def _find_traffic_substitution(
    original: dict,
    activity: ImpactedActivity,
    state: ReplanState,
) -> SubstitutionSuggestion | None:
    """
    Handle traffic issues - suggest alternative routes or pit-stops.
    """
    current_data = state["current_data"]
    
    try:
        # Check alternative transit options
        directions_tool = GoogleMapsTransitTool.directions
        
        loc = original.get("location", {})
        if not loc:
            return None

        # Get alternative routes
        origin = state.get("current_location", {})
        if not origin:
            return None

        # Try different transit modes
        modes = ["transit", "driving", "walking"]
        best_option = None
        
        for mode in modes:
            try:
                result = await directions_tool._arun(
                    origin=f"{origin.get('latitude')},{origin.get('longitude')}",
                    destination=f"{loc.get('latitude')},{loc.get('longitude')}",
                    mode=mode,
                )
                if result:
                    duration = result.get("legs", [{}])[0].get("duration_seconds", float("inf"))
                    if not best_option or duration < best_option.get("duration", float("inf")):
                        best_option = {"mode": mode, "duration": duration, "result": result}
            except Exception:
                continue

        if best_option:
            # Create a modified activity with updated transit
            new_activity = original.copy()
            new_activity["transit_suggestion"] = {
                "recommended_mode": best_option["mode"],
                "duration_minutes": best_option["duration"] // 60,
                "details": best_option["result"],
            }

            # Suggest a pit-stop if needed
            if best_option["duration"] > 3600:  # More than 1 hour
                new_activity["pit_stop"] = {
                    "suggestion": "Consider stopping at a cafe or rest area",
                    "search_query": "cafe rest area near route",
                }

            return SubstitutionSuggestion(
                original_activity_id=activity.activity_id,
                new_activity=new_activity,
                reason=f"Alternative route to avoid traffic. Recommended: {best_option['mode']}",
                confidence_score=0.7,
            )

    except Exception as e:
        logger.error(f"Traffic substitution failed: {e}")
    
    return None


async def _find_crowd_substitution(
    original: dict,
    activity: ImpactedActivity,
    state: ReplanState,
) -> SubstitutionSuggestion | None:
    """
    Find alternative venue when original is too crowded.
    Uses Google Places 'Live Busyness' data.
    """
    current_data = state["current_data"]
    destination = current_data.get("destination_city", current_data.get("destination", ""))
    
    try:
        place_tool = GoogleMapsTransitTool.place_search
        
        # Search for "hidden gems" alternatives
        category = original.get("category", "sightseeing")
        
        # Search for less popular alternatives
        query = f"hidden gem {category} {destination} less crowded"
        results = await place_tool._arun(query=query, radius=5000)
        
        if not results:
            # Try regular search
            query = f"{category} in {destination}"
            results = await place_tool._arun(query=query, radius=5000)

        if not results:
            return None

        # Use LLM to select best alternative
        llm = get_llm(temperature=0.5)
        prompt = ChatPromptTemplate.from_template(SUBSTITUTION_PROMPT)
        
        messages = prompt.format_messages(
            original_activity=str(original),
            trigger_type="crowd",
            trigger_details=state.get("trigger_details", "Venue is very crowded"),
            impact_reason=activity.impact_reason,
            destination=destination,
            preferences=str(state.get("user_preferences", {})),
            time_slot=f"{original.get('start_time', '10:00')} - {original.get('end_time', '12:00')}",
            budget_range=str(original.get("estimated_cost", "moderate")),
            weather_conditions="Not relevant for this substitution",
            nearby_alternatives=str(results[:5]),
        )

        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        new_activity = json.loads(content)
        new_activity["is_hidden_gem"] = True

        return SubstitutionSuggestion(
            original_activity_id=activity.activity_id,
            new_activity=new_activity,
            reason=f"Less crowded alternative: {activity.impact_reason}",
            confidence_score=new_activity.get("confidence_score", 0.75),
        )

    except Exception as e:
        logger.error(f"Crowd substitution failed: {e}")
        return None


async def _find_general_substitution(
    original: dict,
    activity: ImpactedActivity,
    state: ReplanState,
) -> SubstitutionSuggestion | None:
    """Find a general substitution for user-requested changes."""
    current_data = state["current_data"]
    destination = current_data.get("destination_city", current_data.get("destination", ""))
    
    try:
        place_tool = GoogleMapsTransitTool.place_search
        
        category = original.get("category", "sightseeing")
        trigger_details = state.get("trigger_details", "")
        
        # Use trigger details to guide search
        if "skip" in trigger_details.lower() or "remove" in trigger_details.lower():
            # User wants to skip - find alternative
            query = f"popular {category} in {destination}"
        else:
            # Generic alternative
            query = f"{category} activities in {destination}"
        
        results = await place_tool._arun(query=query, radius=5000)
        
        if not results:
            return None

        # Use LLM to select
        llm = get_llm(temperature=0.5)
        prompt = ChatPromptTemplate.from_template(SUBSTITUTION_PROMPT)
        
        messages = prompt.format_messages(
            original_activity=str(original),
            trigger_type="user_request",
            trigger_details=trigger_details,
            impact_reason=activity.impact_reason,
            destination=destination,
            preferences=str(state.get("user_preferences", {})),
            time_slot=f"{original.get('start_time', '10:00')} - {original.get('end_time', '12:00')}",
            budget_range=str(original.get("estimated_cost", "moderate")),
            weather_conditions=str(state.get("weather_data", {})),
            nearby_alternatives=str(results[:5]),
        )

        response = await llm.ainvoke(messages)
        
        import json
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        new_activity = json.loads(content)

        return SubstitutionSuggestion(
            original_activity_id=activity.activity_id,
            new_activity=new_activity,
            reason=f"User-requested change: {activity.impact_reason}",
            confidence_score=new_activity.get("confidence_score", 0.8),
        )

    except Exception as e:
        logger.error(f"General substitution failed: {e}")
        return None


async def transit_update_node(state: ReplanState) -> dict:
    """
    Update transit details for all modified activities.
    
    Fetches exact exit numbers and walking directions.
    """
    logger.info("Updating transit details")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=ReplanStep.TRANSIT_UPDATE,
            progress=70,
            message="🚇 Updating transit information...",
        )

    substitutions = state.get("substitutions", [])
    changes = state.get("changes", [])
    current_data = state["current_data"]

    if not substitutions:
        return {
            "current_step": ReplanStep.MONETIZATION_UPDATE,
            "step_progress": 80,
            "step_message": "No transit updates needed",
        }

    directions_tool = GoogleMapsTransitTool.directions

    updated_changes = []
    for i, change in enumerate(changes):
        if change.change_type != "substitution" or not change.new_item:
            updated_changes.append(change)
            continue

        try:
            new_activity = change.new_item
            new_loc = new_activity.get("location", {})
            
            if not new_loc:
                updated_changes.append(change)
                continue

            # Get transit to this activity from previous activity
            day_plans = current_data.get("daily_plans", [])
            day_plan = next(
                (p for p in day_plans if p.get("day_number") == change.day_number),
                None
            )
            
            if day_plan:
                activities = day_plan.get("activities", [])
                # Find index of this activity
                for idx, act in enumerate(activities):
                    if act.get("title") == change.original_item.get("title"):
                        # Get previous activity
                        if idx > 0:
                            prev_act = activities[idx - 1]
                            prev_loc = prev_act.get("location", {})
                            
                            if prev_loc:
                                result = await directions_tool._arun(
                                    origin=prev_loc.get("name", ""),
                                    destination=new_loc.get("name", ""),
                                    mode="transit",
                                )
                                
                                if result:
                                    new_activity["transit_from_previous"] = {
                                        "mode": "transit",
                                        "duration_minutes": result.get("legs", [{}])[0].get("duration_seconds", 0) // 60,
                                        "exit_info": result.get("exit_info"),
                                        "steps": result.get("steps", [])[:3],  # First 3 steps
                                    }
                        break

            change.transit_updated = True
            change.new_item = new_activity
            updated_changes.append(change)

        except Exception as e:
            logger.warning(f"Transit update failed for change: {e}")
            updated_changes.append(change)

    return {
        "changes": updated_changes,
        "current_step": ReplanStep.MONETIZATION_UPDATE,
        "step_progress": 80,
        "step_message": "Transit details updated",
    }


async def monetization_update_node(state: ReplanState) -> dict:
    """
    Update affiliate links for new activities.
    """
    logger.info("Updating monetization links")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=ReplanStep.MONETIZATION_UPDATE,
            progress=88,
            message="💰 Updating booking links...",
        )

    changes = state.get("changes", [])
    
    if not changes:
        return {
            "current_step": ReplanStep.FINALIZATION,
            "step_progress": 92,
        }

    # Update affiliate links for substitutions
    for change in changes:
        if change.change_type != "substitution" or not change.new_item:
            continue

        try:
            new_activity = change.new_item
            
            # Check if this is a bookable activity
            if new_activity.get("requires_booking"):
                # Generate affiliate link via Travelpayouts
                # For now, we'll just mark it as needing a link
                new_activity["affiliate_url_pending"] = True
            
            change.affiliate_links_updated = True
            change.new_item = new_activity

        except Exception as e:
            logger.warning(f"Monetization update failed: {e}")

    return {
        "changes": changes,
        "current_step": ReplanStep.FINALIZATION,
        "step_progress": 92,
        "step_message": "Booking links updated",
    }


async def finalization_node(state: ReplanState) -> dict:
    """
    Finalize the replanned itinerary and create the updated data.
    """
    logger.info("Finalizing replan")

    if state.get("progress_callback"):
        await state["progress_callback"](
            step=ReplanStep.FINALIZATION,
            progress=95,
            message="✨ Finalizing your updated itinerary...",
        )

    current_data = state["current_data"].copy()
    changes = state.get("changes", [])
    substitutions = state.get("substitutions", [])

    # Apply changes to the itinerary data
    for sub in substitutions:
        _apply_substitution_to_data(current_data, sub)

    # Calculate summary
    summary = ReplanSummary(
        total_changes=len(changes),
        activities_substituted=sum(1 for c in changes if c.change_type == "substitution"),
        activities_rescheduled=sum(1 for c in changes if c.change_type == "rescheduled"),
        activities_removed=sum(1 for c in changes if c.change_type == "removed"),
        activities_added=sum(1 for c in changes if c.change_type == "added"),
        routes_updated=sum(1 for c in changes if c.transit_updated),
        estimated_time_saved_minutes=0,  # Calculate if needed
        estimated_cost_difference=Decimal("0"),  # Calculate if needed
    )

    # Update version
    new_version = state["current_version"] + 1
    current_data["version"] = new_version
    current_data["last_updated"] = datetime.now(timezone.utc).isoformat()

    return {
        "updated_data": current_data,
        "new_version": new_version,
        "summary": summary,
        "current_step": ReplanStep.FINALIZATION,
        "step_progress": 100,
        "step_message": "🎉 Your itinerary has been updated!",
    }


async def error_handling_node(state: ReplanState) -> dict:
    """Handle errors in the replan workflow."""
    logger.error(f"Replan error: {state.get('error')}")
    
    return {
        "step_message": f"Error: {state.get('error', 'Unknown error')}",
    }


# ============ Helper Functions ============


def _format_days_for_analysis(daily_plans: list) -> str:
    """Format daily plans for LLM analysis."""
    lines = []
    for plan in daily_plans:
        day_num = plan.get("day_number", "?")
        day_date = plan.get("date", "")
        lines.append(f"\n=== Day {day_num} ({day_date}) ===")
        
        for idx, act in enumerate(plan.get("activities", [])):
            time_str = act.get("start_time", "")
            title = act.get("title", "Unknown")
            category = act.get("category", "")
            location = act.get("location", {}).get("name", "")
            is_outdoor = "outdoor" in title.lower() or category in ["sightseeing", "nature"]
            
            lines.append(f"  [{idx}] {time_str} - {title}")
            lines.append(f"      Category: {category}, Location: {location}")
            lines.append(f"      Outdoor: {is_outdoor}")
    
    return "\n".join(lines)


def _get_activity_from_data(data: dict, day_number: int, activity_index: int) -> dict | None:
    """Get a specific activity from itinerary data."""
    daily_plans = data.get("daily_plans", [])
    for plan in daily_plans:
        if plan.get("day_number") == day_number:
            activities = plan.get("activities", [])
            if 0 <= activity_index < len(activities):
                return activities[activity_index]
    return None


def _apply_substitution_to_data(data: dict, sub: SubstitutionSuggestion) -> None:
    """Apply a substitution to the itinerary data."""
    daily_plans = data.get("daily_plans", [])
    
    for plan in daily_plans:
        activities = plan.get("activities", [])
        for idx, act in enumerate(activities):
            # Match by activity ID or title
            act_id = act.get("id", act.get("title", ""))
            if act_id == sub.original_activity_id or act.get("title") == sub.original_activity_id:
                # Replace activity
                new_act = sub.new_activity.copy()
                new_act["replaced_from"] = act.get("title")
                new_act["replacement_reason"] = sub.reason
                activities[idx] = new_act
                return


async def _fetch_weather_data(itinerary_data: dict) -> dict | None:
    """Fetch current weather data for the destination."""
    try:
        tool = WeatherTool.forecast
        destination = itinerary_data.get("destination_city", itinerary_data.get("destination", ""))
        
        if not destination:
            return None

        result = await tool._arun(
            location=destination,
            start_date=date.today().isoformat(),
            end_date=(date.today() + timedelta(days=2)).isoformat(),
            units="metric",
        )
        return result
    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}")
        return None


async def _fetch_traffic_data(itinerary_data: dict, current_location: dict | None) -> dict | None:
    """Fetch traffic data for current route."""
    # Note: Would integrate with Google Maps Traffic API
    # For now, return placeholder
    return {"status": "traffic_data_placeholder"}


async def _fetch_crowd_data(itinerary_data: dict) -> dict | None:
    """Fetch crowd/busyness data for venues."""
    # Note: Would integrate with Google Places Popular Times
    # For now, return placeholder
    return {"status": "crowd_data_placeholder"}


# ============ Graph Builder ============


def build_replan_graph() -> StateGraph:
    """
    Build the LangGraph workflow for smart replanning.
    
    Flow:
    1. load_state -> Load existing itinerary
    2. impact_analysis -> Identify affected activities
    3. dynamic_substitution -> Find replacements based on trigger
    4. transit_update -> Update transit details
    5. monetization_update -> Update affiliate links
    6. finalization -> Create updated itinerary
    """
    workflow = StateGraph(ReplanState)

    # Add nodes
    workflow.add_node("load_state", load_state_node)
    workflow.add_node("impact_analysis", impact_analysis_node)
    workflow.add_node("dynamic_substitution", dynamic_substitution_node)
    workflow.add_node("transit_update", transit_update_node)
    workflow.add_node("monetization_update", monetization_update_node)
    workflow.add_node("finalization", finalization_node)
    workflow.add_node("error_handling", error_handling_node)

    # Set entry point
    workflow.set_entry_point("load_state")

    # Add edges
    def should_continue(state: ReplanState) -> Literal["continue", "error", "end"]:
        if state.get("error"):
            return "error"
        if state["current_step"] == ReplanStep.FINALIZATION and state.get("updated_data"):
            return "end"
        return "continue"

    workflow.add_conditional_edges(
        "load_state",
        should_continue,
        {
            "continue": "impact_analysis",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "impact_analysis",
        should_continue,
        {
            "continue": "dynamic_substitution",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "dynamic_substitution",
        should_continue,
        {
            "continue": "transit_update",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "transit_update",
        should_continue,
        {
            "continue": "monetization_update",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "monetization_update",
        should_continue,
        {
            "continue": "finalization",
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "finalization",
        should_continue,
        {
            "continue": END,
            "error": "error_handling",
            "end": END,
        },
    )

    workflow.add_edge("error_handling", END)

    return workflow


# Create checkpointer for state persistence
memory_checkpointer = MemorySaver()

# Compile the graph with checkpointing
replan_graph = build_replan_graph().compile(checkpointer=memory_checkpointer)


# ============ Public Interface ============


async def run_replan(
    itinerary_id: str,
    current_data: dict,
    current_version: int,
    trigger_type: str,
    trigger_reason: str,
    trigger_details: str | None = None,
    current_location: dict | None = None,
    affected_day: int | None = None,
    affected_activity_ids: list[str] | None = None,
    user_preferences: dict | None = None,
    user_id: str | None = None,
    progress_callback: Any | None = None,
) -> dict | None:
    """
    Run the replan workflow and return updated itinerary.
    
    Args:
        itinerary_id: ID of the itinerary to replan
        current_data: Current itinerary data (AIFullItinerary)
        current_version: Current version number
        trigger_type: Type of trigger (weather, traffic, crowd, user_request)
        trigger_reason: user_initiated or system_proactive
        trigger_details: Additional trigger details
        current_location: User's GPS location
        affected_day: Specific day to replan
        affected_activity_ids: Specific activities to consider
        user_preferences: Additional preferences
        user_id: User ID
        progress_callback: Callback for progress updates
        
    Returns:
        Dict with updated_data, changes, summary, etc.
    """
    initial_state: ReplanState = {
        "itinerary_id": itinerary_id,
        "user_id": user_id,
        "trigger_type": trigger_type,
        "trigger_reason": trigger_reason,
        "trigger_details": trigger_details,
        "current_location": current_location,
        "affected_day": affected_day,
        "affected_activity_ids": affected_activity_ids,
        "user_preferences": user_preferences,
        "current_data": current_data,
        "current_version": current_version,
        "messages": [],
        "current_step": ReplanStep.LOADING_STATE,
        "step_progress": 0,
        "step_message": "Starting...",
        "impacted_activities": [],
        "weather_data": None,
        "traffic_data": None,
        "crowd_data": None,
        "substitutions": [],
        "changes": [],
        "summary": None,
        "updated_data": None,
        "new_version": current_version + 1,
        "error": None,
        "is_critical": False,
        "alert_message": None,
        "progress_callback": progress_callback,
    }

    try:
        # Run with checkpointer for state persistence
        config = {"configurable": {"thread_id": itinerary_id}}
        final_state = await replan_graph.ainvoke(initial_state, config)

        if final_state.get("error"):
            logger.error(f"Replan failed: {final_state['error']}")
            return {
                "success": False,
                "error": final_state["error"],
            }

        return {
            "success": True,
            "updated_data": final_state.get("updated_data"),
            "new_version": final_state.get("new_version"),
            "changes": [c.model_dump() for c in final_state.get("changes", [])],
            "summary": final_state.get("summary").model_dump() if final_state.get("summary") else None,
            "is_critical": final_state.get("is_critical", False),
            "alert_message": final_state.get("alert_message"),
        }

    except Exception as e:
        logger.error(f"Replan execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
