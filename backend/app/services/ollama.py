import base64
import json
import re

import httpx

from ..config import settings

FENCE = re.compile(r"```(?:json)?", re.IGNORECASE)

CAPTION_RULE = (
    "caption 用一句不超过 40 字的中文描述：拍到了什么、所处场景或氛围，"
    "不要猜测人物身份，不要加引号或“这张照片”之类的前缀；"
    "keywords 给 3 到 6 个中文短词（2-6 字），用于之后检索，不要带 # 号。"
)


class OllamaError(RuntimeError):
    pass


async def generate(model: str, prompt: str, images: list[bytes] | None = None) -> str:
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 600},
    }
    if images:
        payload["images"] = [base64.b64encode(image).decode("ascii") for image in images]

    try:
        async with httpx.AsyncClient(base_url=settings.ollama_url.rstrip("/"), timeout=300) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise OllamaError(f"调用 Ollama 失败: {exc}") from exc

    text = (data.get("response") or "").strip()
    if not text:
        raise OllamaError("Ollama 返回了空内容")
    return text


def _parse_result(text: str) -> tuple[str, list[str]]:
    """解析模型输出的 JSON；模型没按格式回答时退化为整段当配文。"""
    cleaned = FENCE.sub("", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            caption = str(data.get("caption") or "").strip()
            raw_keywords = data.get("keywords") or []
            keywords: list[str] = []
            for item in raw_keywords if isinstance(raw_keywords, list) else []:
                word = str(item).strip().lstrip("#").strip()
                if word and word not in keywords:
                    keywords.append(word[:16])
            if caption:
                return caption[:200], keywords[:8]
    fallback = next((line.strip() for line in cleaned.splitlines() if line.strip()), "")
    return fallback[:200], []


async def analyze_image(image: bytes, note_hint: str = "") -> tuple[str, list[str]]:
    """单张图片：返回（配文，关键词）。"""
    prompt = (
        "你是生活记录助手。请只输出一个 JSON 对象，不要任何解释、不要代码块标记，格式：\n"
        '{"caption": "……", "keywords": ["……", "……"]}\n' + CAPTION_RULE
    )
    if note_hint.strip():
        prompt += f"\n当天的文字记录是：{note_hint.strip()[:200]}。可以结合它，但不要照抄。"
    return _parse_result(await generate(settings.ollama_vlm_model, prompt, images=[image]))


async def merge_video_clip(frames: list[str], note_hint: str = "") -> tuple[str, list[str]]:
    """把视频多帧的描述合并成一条视频配文与关键词。"""
    material = "\n".join(f"第 {index + 1} 帧：{text}" for index, text in enumerate(frames) if text)
    prompt = (
        "你是生活记录助手。下面是一个视频按时间先后抽取的几帧画面描述，"
        "请把它们合并成对整段视频的描述。只输出一个 JSON 对象，不要任何解释、不要代码块标记，格式：\n"
        '{"caption": "……", "keywords": ["……", "……"]}\n'
        "caption 用一句不超过 40 字的中文概括视频里发生了什么、场景或氛围；"
        "keywords 给 3 到 6 个中文短词（2-6 字），不要带 # 号。\n"
        f"画面描述：\n{material[:3000]}"
    )
    if note_hint.strip():
        prompt += f"\n当天的文字记录是：{note_hint.strip()[:200]}。可以结合它，但不要照抄。"
    return _parse_result(await generate(settings.ollama_vlm_model, prompt))


async def summarize_period(label: str, material: str) -> str:
    prompt = (
        f"你是生活记录助手。下面是 {label} 的每日记录与照片描述。"
        "请只基于这些内容，用中文输出 Markdown，结构如下：\n"
        "## 这段时间的三句话\n用三句话概括这段时间的生活。\n"
        "## 值得记住的片段\n列出 3 到 5 条，每条不超过 30 字。\n"
        "## 一句话回顾\n写一句温和、具体的总结。\n"
        "不要编造没有出现的事件，不要使用夸张的抒情。\n\n"
        f"素材：\n{material[:12000]}"
    )
    return await generate(settings.ollama_text_model, prompt)
