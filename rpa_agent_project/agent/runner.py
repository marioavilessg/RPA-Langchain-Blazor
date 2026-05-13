from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from shared.config import load_environment
from shared.templating import render_value


load_environment()

BASE_DIR = Path(__file__).resolve().parents[1]
PROCEDURES_DIR = BASE_DIR / "procedures"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "si", "s"}


def resolve_workflow_path(workflow_ref: str | Path) -> Path:
    """Resolve either a workflow id or a JSON path to an absolute path."""
    ref = Path(str(workflow_ref))

    if ref.is_absolute():
        return ref

    ref_text = str(workflow_ref)
    looks_like_path = ref.suffix == ".json" or any(sep in ref_text for sep in ("/", "\\"))
    if looks_like_path:
        return (BASE_DIR / ref).resolve()

    return (PROCEDURES_DIR / f"{ref_text}.json").resolve()


def load_workflow(workflow_ref: str | Path) -> dict[str, Any]:
    workflow_path = resolve_workflow_path(workflow_ref)
    if not workflow_path.exists():
        raise FileNotFoundError(f"No existe el workflow: {workflow_path}")

    with workflow_path.open("r", encoding="utf-8") as f:
        workflow = json.load(f)

    workflow["_path"] = str(workflow_path)
    return workflow


def _selector(target: dict[str, Any]) -> str:
    by = (target.get("by") or "css").lower()
    value = str(target.get("value", ""))

    if by == "id":
        return f"#{value}"
    if by == "name":
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'[name="{escaped}"]'
    if by == "css":
        return value

    raise ValueError(f"Selector no soportado: by={by}")


def _params_with_env(params: dict[str, Any]) -> dict[str, Any]:
    template_params: dict[str, Any] = dict(os.environ)
    template_params.update(params)
    return template_params


def run_workflow(
    workflow_ref: str | Path,
    params: dict[str, Any],
    *,
    headless: bool | None = None,
    timeout_ms: int = 10000,
) -> dict[str, Any]:
    """Execute a workflow JSON with Playwright and return a structured summary."""
    started_at = time.perf_counter()
    workflow = load_workflow(workflow_ref)
    workflow_id = workflow.get("id", str(workflow_ref))
    template_params = _params_with_env(params)
    form_url = os.getenv("FORM_URL") or workflow["url"]
    url = render_value(form_url, template_params)
    headless = _as_bool(os.getenv("RPA_HEADLESS"), default=False) if headless is None else headless

    result: dict[str, Any] = {
        "ok": False,
        "workflow_id": workflow_id,
        "workflow_path": workflow.get("_path"),
        "url": url,
        "duration_seconds": 0,
        "last_text": None,
        "error": None,
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                page = browser.new_page()
                page.set_default_timeout(timeout_ms)

                print(f"[RPA] Navegando a {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                for index, step in enumerate(workflow.get("steps", []), start=1):
                    step_type = step.get("type")
                    target = step.get("target") or {}
                    selector = _selector(target) if target else None
                    print(f"[RPA] Step {index}: {step_type}" + (f" -> {selector}" if selector else ""))

                    if step_type == "wait":
                        page.wait_for_timeout(int(step.get("ms", 0)))

                    elif step_type == "type":
                        if not selector:
                            raise ValueError("Step type necesita target")
                        text = render_value(step.get("value", ""), template_params)
                        page.locator(selector).fill(str(text), timeout=timeout_ms)

                    elif step_type == "select":
                        if not selector:
                            raise ValueError("Step select necesita target")
                        option = render_value(step.get("value", ""), template_params)
                        page.locator(selector).select_option(str(option), timeout=timeout_ms)

                    elif step_type == "click":
                        if not selector:
                            raise ValueError("Step click necesita target")
                        page.locator(selector).click(timeout=timeout_ms)

                    elif step_type == "wait_for_text":
                        if not selector:
                            raise ValueError("Step wait_for_text necesita target")
                        contains = str(render_value(step.get("contains", ""), template_params))
                        locator = page.locator(selector).filter(has_text=contains)
                        locator.wait_for(state="visible", timeout=timeout_ms)
                        result["last_text"] = locator.first.inner_text(timeout=timeout_ms)

                    else:
                        raise ValueError(f"Tipo de step no soportado: {step_type}")

                result["ok"] = True
                return result
            finally:
                browser.close()

    except (FileNotFoundError, ValueError, PlaywrightTimeoutError, PlaywrightError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    finally:
        result["duration_seconds"] = round(time.perf_counter() - started_at, 3)
