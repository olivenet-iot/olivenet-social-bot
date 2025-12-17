"""
Publisher Agent - Yayıncı
İçeriği sosyal medyaya paylaşır
"""

import json
from datetime import datetime
from typing import Dict, Any
from .base_agent import BaseAgent
from app.database import update_post, log_agent_action

class PublisherAgent(BaseAgent):
    """Yayıncı - içeriği sosyal medyaya paylaşır"""

    def __init__(self):
        super().__init__("publisher")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ana yürütme metodu"""
        action = input_data.get("action", "publish")

        if action == "publish":
            return await self.publish(input_data)
        elif action == "schedule":
            return await self.schedule(input_data)
        else:
            return {"error": f"Unknown action: {action}"}

    async def publish(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """İçeriği hemen yayınla"""
        self.log("İçerik yayınlanıyor...")

        post_id = input_data.get("post_id")
        post_text = input_data.get("post_text", "")
        image_path = input_data.get("image_path")
        video_path = input_data.get("video_path")
        platform = input_data.get("platform", "facebook")

        result = {
            "success": False,
            "platform": platform,
            "post_id": post_id
        }

        try:
            if platform == "facebook":
                if video_path:
                    # Video paylaş
                    from app.facebook_helper import post_video_to_facebook
                    fb_result = await post_video_to_facebook(video_path, post_text)
                elif image_path:
                    # Fotoğraf paylaş
                    from app.facebook_helper import post_to_facebook
                    fb_result = await post_to_facebook(image_path, post_text)
                else:
                    fb_result = {"success": False, "error": "No media provided"}

                if fb_result.get("success"):
                    result["success"] = True
                    result["facebook_post_id"] = fb_result.get("post_id")

                    # Database güncelle
                    if post_id:
                        update_post(
                            post_id,
                            status="published",
                            published_at=datetime.now(),
                            facebook_post_id=fb_result.get("post_id")
                        )
                else:
                    result["error"] = fb_result.get("error", "Unknown error")

            # TODO: Instagram desteği eklenecek
            elif platform == "instagram":
                result["error"] = "Instagram desteği henüz eklenmedi"

            log_agent_action(
                agent_name=self.name,
                action="publish",
                input_data={"post_id": post_id, "platform": platform},
                output_data=result,
                success=result.get("success", False)
            )

            if result["success"]:
                self.log(f"İçerik yayınlandı! Platform: {platform}")
            else:
                self.log(f"Yayınlama başarısız: {result.get('error', 'N/A')}")

            return result

        except Exception as e:
            result["error"] = str(e)
            log_agent_action(
                agent_name=self.name,
                action="publish",
                success=False,
                error_message=str(e)
            )
            return result

    async def schedule(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """İçeriği zamanla"""
        self.log("İçerik zamanlanıyor...")

        post_id = input_data.get("post_id")
        scheduled_time = input_data.get("scheduled_time")  # datetime string

        if post_id and scheduled_time:
            update_post(
                post_id,
                status="scheduled",
                scheduled_at=scheduled_time
            )

            log_agent_action(
                agent_name=self.name,
                action="schedule",
                input_data={"post_id": post_id, "scheduled_time": str(scheduled_time)},
                output_data={"success": True},
                success=True
            )

            self.log(f"İçerik zamanlandı: {scheduled_time}")
            return {"success": True, "scheduled_at": str(scheduled_time)}

        return {"success": False, "error": "Missing post_id or scheduled_time"}
