from astrbot.api.message_components import *
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import aiohttp
import asyncio
import random
import json

@register("mod-qwen-image", "Qwen文生图", "使用硅基流动的Qwen-Image模型文生图。使用 /qwen <提示词> 生成图片。", "1.0")
class ModQwenImage(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.api_key = config.get("api_key")
        self.model = config.get("model")
        self.num_inference_steps = config.get("num_inference_steps")
        self.size = config.get("size")
        base_api_url = config.get("api_url")
        self.api_url = base_api_url.rstrip('/') + "/v1/images/generations"
        self.seed = config.get("seed")

        if not self.api_key or self.api_key == "API_Key":
            raise ValueError("API 密钥未配置或无效，请在后台插件配置中填写正确的 API Key。")

    @filter.command("qwen")
    async def generate_image(self, event: AstrMessageEvent):
        # 1. 获取用户输入的提示词
        full_message = event.message_obj.message_str
        parts = full_message.split(" ", 1)
        prompt = parts[1].strip() if len(parts) > 1 else ""

        if not prompt:
            yield event.plain_result("\n请提供提示词！使用方法：/qwen <提示词>")
            return
        try:
            # 2. 处理随机种子
            try:
                if self.seed == "随机" or not self.seed:
                    current_seed = random.randint(1, 2147483647)
                else:
                    current_seed = int(self.seed)
            except (ValueError, TypeError):
                current_seed = random.randint(1, 2147483647)

            # 3. 调用文生图API
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}'
                }
                
                data = {
                    "prompt": prompt,
                    "model": self.model,
                    "size": self.size,
                    "num_inference_steps": self.num_inference_steps,
                    "seed": current_seed
                }
                
                async with session.post(self.api_url, headers=headers, json=data) as response:
                    response_text = await response.text()
                    
                    # 4. 尝试解析JSON
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        yield event.plain_result(f"\n生成图片失败: API返回无效数据 - {response_text[:100]}")
                        return

                    # 5. 处理API错误
                    if response.status != 200:
                        error_msg = response_data.get("error", {}).get("message", str(response_data))
                        yield event.plain_result(f"\n生成图片失败 (HTTP {response.status}): {error_msg}")
                        return

                    # 6. 从 'images' 字段中提取URL
                    if not isinstance(response_data, dict) or "images" not in response_data or not response_data["images"]:
                        yield event.plain_result(f"\n生成图片失败: API返回格式异常 - {str(response_data)[:100]}")
                        return
                        
                    image_url = response_data['images'][0]['url']
                    returned_seed = response_data.get('seed', current_seed) # 优先使用API返回的seed
                    
                    # 7. 发送结果
                    yield event.chain_result([Image.fromURL(image_url)])

        except Exception as e:
            yield event.plain_result(f"\n生成图片时发生未知错误: {str(e)}")
