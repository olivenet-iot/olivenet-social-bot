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
                    fb_result = await post_video_to_facebook(
                        message=post_text,
                        video_path=video_path
                    )
                elif image_path:
                    # Fotoğraf paylaş
                    from app.facebook_helper import post_with_photo_to_facebook
                    fb_result = await post_with_photo_to_facebook(
                        message=post_text,
                        image_path=image_path
                    )
                else:
                    fb_result = {"error": "No media provided"}

                # Facebook API "id" döndürür, "success" değil
                if fb_result.get("id"):
                    result["success"] = True
                    result["facebook_post_id"] = fb_result.get("id")

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

            elif platform == "instagram":
                # Instagram için görsel CDN'e yüklenmeli (public URL gerekli)
                from app.instagram_helper import (
                    post_photo_to_instagram,
                    post_video_to_instagram,
                    upload_image_to_cdn
                )

                if video_path:
                    # Video için CDN URL gerekli
                    # Şimdilik sadece public URL destekleniyor
                    ig_result = {"success": False, "error": "Instagram video için CDN URL gerekli"}

                elif image_path:
                    # Görseli CDN'e yükle
                    image_url = await upload_image_to_cdn(image_path)

                    if image_url:
                        ig_result = await post_photo_to_instagram(
                            image_url=image_url,
                            caption=post_text
                        )
                    else:
                        ig_result = {"success": False, "error": "Gorsel CDN'e yuklenemedi"}
                else:
                    ig_result = {"error": "No media provided"}

                if ig_result.get("success") or ig_result.get("id"):
                    result["success"] = True
                    result["instagram_post_id"] = ig_result.get("id")

                    if post_id:
                        update_post(
                            post_id,
                            status="published",
                            published_at=datetime.now(),
                            instagram_post_id=ig_result.get("id")
                        )
                else:
                    result["error"] = ig_result.get("error", "Unknown error")

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
