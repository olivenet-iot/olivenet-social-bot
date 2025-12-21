from .models import init_database, create_default_strategy, get_connection
from .crud import (
    # Posts
    create_post, update_post, get_post, get_posts_by_status,
    get_scheduled_posts, get_published_posts,
    # Analytics
    record_analytics, get_post_analytics, get_analytics_summary,
    update_post_analytics, get_posts_with_analytics,
    # Strategy
    get_current_strategy, update_strategy,
    # Calendar
    create_calendar_entry, get_week_calendar, get_todays_calendar, update_calendar_status,
    # Logs
    log_agent_action, get_agent_logs,
    # Hook Performance
    update_hook_performance, get_best_performing_hooks,
    get_hook_performance_by_type, get_hook_recommendations,
    # A/B Testing
    log_ab_test_result, update_ab_test_actual_performance,
    get_ab_test_results, get_ab_test_learnings
)

# Database'i initialize et
init_database()
create_default_strategy()
