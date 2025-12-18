"""
Publisher Agent - Yayıncı
İçeriği Facebook ve Instagram'a paylaşır
"""

import json
import os
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
        """İçeriği Facebook + Instagram'a yayınla"""
        self.log("İçerik yayınlanıyor...")
        
        post_id = input_data.get("post_id")
        post_text = input_data.get("post_text", "")
        image_path = input_data.get("image_path")
        video_path = input_data.get("video_path")
        platform = input_data.get("platform", "both")  # facebook, instagram, both
        
        result = {
            "success": False,
            "post_id": post_id,
            "platforms": {}
        }
        
        try:
            # ===== FACEBOOK =====
            if platform in ["facebook", "both"]:
                fb_result = await self._publish_to_facebook(post_text, image_path, video_path)
                result["platforms"]["facebook"] = fb_result
                
                if fb_result.get("success"):
                    result["facebook_post_id"] = fb_result.get("id")
                    self.log(f"✅ Facebook'a yayınlandı: {fb_result.get('id', 'N/A')}")
                else:
                    self.log(f"❌ Facebook hatası: {fb_result.get('error', 'N/A')}")
            
            # ===== INSTAGRAM =====
            if platform in ["instagram", "both"]:
                ig_result = await self._publish_to_instagram(post_text, image_path, video_path)
                result["platforms"]["instagram"] = ig_result
                
                if ig_result.get("success"):
                    result["instagram_post_id"] = ig_result.get("id")
                    self.log(f"✅ Instagram'a yayınlandı: {ig_result.get('id', 'N/A')}")
                else:
                    self.log(f"❌ Instagram hatası: {ig_result.get('error', 'N/A')}")
            
            # En az bir platform başarılıysa success
            fb_ok = result["platforms"].get("facebook", {}).get("success", False)
            ig_ok = result["platforms"].get("instagram", {}).get("success", False)
            result["success"] = fb_ok or ig_ok
            
            # Database güncelle
            if post_id and result["success"]:
                update_data = {
                    "status": "published",
                    "published_at": datetime.now()
                }
                if fb_ok:
                    update_data["facebook_post_id"] = result["platforms"]["facebook"].get("id")
                if ig_ok:
                    update_data["instagram_post_id"] = result["platforms"]["instagram"].get("id")
                
                update_post(post_id, **update_data)
            
            log_agent_action(
                agent_name=self.name,
                action="publish",
                input_data={"post_id": post_id, "platform": platform},
                output_data=result,
                success=result["success"]
            )
            
            return result
            
        except Exception as e:
            self.log(f"Yayınlama hatası: {str(e)}")
            result["error"] = str(e)
            log_agent_action(
                agent_name=self.name,
                action="publish",
                success=False,
                error_message=str(e)
            )
            return result
    
    async def _publish_to_facebook(self, post_text: str, image_path: str = None, video_path: str = None) -> Dict[str, Any]:
        """Facebook'a paylaş"""
        try:
            from app.facebook_helper import post_with_photo_to_facebook, post_video_to_facebook
            
            if video_path and os.path.exists(video_path):
                fb_result = await post_video_to_facebook(message=post_text, video_path=video_path)
            elif image_path and os.path.exists(image_path):
                fb_result = await post_with_photo_to_facebook(message=post_text, image_path=image_path)
            else:
                return {"success": False, "error": "No media provided for Facebook"}
            
            # Facebook API "id" döndürür
            if fb_result.get("id"):
                return {"success": True, "id": fb_result.get("id")}
            else:
                return {"success": False, "error": fb_result.get("error", "Unknown error")}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _publish_to_instagram(self, post_text: str, image_path: str = None, video_path: str = None) -> Dict[str, Any]:
        """Instagram'a paylaş"""
        try:
            from app.instagram_helper import upload_image_to_cdn, post_photo_to_instagram
            
            # Instagram public URL istiyor - önce CDN'e yükle
            if video_path and os.path.exists(video_path):
                # Video için şimdilik desteklenmiyor
                return {"success": False, "error": "Instagram video henuz desteklenmiyor"}
            
            elif image_path and os.path.exists(image_path):
                # Resmi CDN'e yükle (imgbb)
                cdn_result = await upload_image_to_cdn(image_path)
                
                if not cdn_result:
                    return {"success": False, "error": "CDN upload failed"}
                
                image_url = cdn_result
                self.log(f"CDN URL: {image_url[:50]}...")
                
                # Instagram'a paylaş
                ig_result = await post_photo_to_instagram(image_url=image_url, caption=post_text)
                return ig_result
            
            else:
                return {"success": False, "error": "No media provided for Instagram"}
                
        except ImportError as e:
            return {"success": False, "error": f"Instagram helper import error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def schedule(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """İçeriği zamanla"""
        self.log("İçerik zamanlanıyor...")
        
        post_id = input_data.get("post_id")
        scheduled_time = input_data.get("scheduled_time")
        
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
