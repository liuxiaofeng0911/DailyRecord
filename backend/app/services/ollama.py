import base64

import httpx

from ..config import settings


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


async def describe_image(image: bytes, note_hint: str = "") -> str:
    prompt = (
        "你是生活记录助手。请用一句不超过 40 个字的中文描述这张照片："
        "拍到了什么、所处的场景或氛围。只输出描述本身，不要猜测人物身份，"
        "不要加引号、编号或“这张照片”之类的前缀。"
    )
    if note_hint.strip():
        prompt += f"\n当天的文字记录是：{note_hint.strip()[:200]}。可以结合它，但不要照抄。"
    return await generate(settings.ollama_vlm_model, prompt, images=[image])


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
