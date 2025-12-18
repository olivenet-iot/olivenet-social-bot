from .models import init_database, create_default_strategy, get_connection
from .crud import (
    # Posts
    create_post, update_post, get_post, get_posts_by_status,
    get_scheduled_posts, get_published_posts,
    # Analytics
    record_analytics, get_post_analytics, get_analytics_summary,
    # Strategy
    get_current_strategy, update_strategy,
    # Calendar
    create_calendar_entry, get_week_calendar, get_todays_calendar, update_calendar_status,
    # Logs
    log_agent_action, get_agent_logs
)

# Database'i initialize et
init_database()
create_default_strategy()
