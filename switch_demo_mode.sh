#!/bin/bash
# ==============================================================================
# Switch between Production and Demo modes
# ==============================================================================

set -e

COMPOSE_FILE="docker-compose.yml"
MODE=$1

print_usage() {
    echo "Usage: $0 [demo|production]"
    echo ""
    echo "Modes:"
    echo "  demo        - 30MB threshold (~45 min to archive)"
    echo "  production  - 300MB threshold (~7 hours to archive, assignment compliant)"
    echo ""
    echo "Examples:"
    echo "  $0 demo         # Switch to demo mode"
    echo "  $0 production   # Switch to production mode"
    exit 1
}

if [ -z "$MODE" ]; then
    print_usage
fi

echo "🔄 Switching to $MODE mode..."
echo ""

case "$MODE" in
    demo)
        echo "🎬 DEMO MODE"
        echo "  - Archival threshold: 30 MB"
        echo "  - Time to trigger: ~45 minutes"
        echo "  - Use for: presentations, recordings, demos"
        echo ""
        
        # Update docker-compose.yml
        sed -i.bak 's/- DEMO_MODE=false/- DEMO_MODE=true/' "$COMPOSE_FILE"
        
        echo "✅ Updated docker-compose.yml"
        echo ""
        echo "Recreating Airflow container to apply changes..."
        docker compose stop airflow
        docker compose rm -f airflow
        docker compose up -d airflow
        
        sleep 15
        
        # Verify
        CURRENT_MODE=$(docker exec airflow printenv DEMO_MODE 2>/dev/null || echo "false")
        if [ "$CURRENT_MODE" = "true" ]; then
            echo "✅ Demo mode activated!"
        else
            echo "⚠️  Warning: Could not verify demo mode. Check container logs."
        fi
        ;;
        
    production)
        echo "🏢 PRODUCTION MODE"
        echo "  - Archival threshold: 300 MB"
        echo "  - Time to trigger: ~7 hours"
        echo "  - Use for: assignment compliance, normal operation"
        echo ""
        
        # Update docker-compose.yml
        sed -i.bak 's/- DEMO_MODE=true/- DEMO_MODE=false/' "$COMPOSE_FILE"
        
        echo "✅ Updated docker-compose.yml"
        echo ""
        echo "Recreating Airflow container to apply changes..."
        docker compose stop airflow
        docker compose rm -f airflow
        docker compose up -d airflow
        
        sleep 15
        
        # Verify
        CURRENT_MODE=$(docker exec airflow printenv DEMO_MODE 2>/dev/null || echo "true")
        if [ "$CURRENT_MODE" = "false" ]; then
            echo "✅ Production mode activated!"
        else
            echo "⚠️  Warning: Could not verify production mode. Check container logs."
        fi
        ;;
        
    *)
        echo "❌ Invalid mode: $MODE"
        print_usage
        ;;
esac

echo ""
echo "📊 Current Configuration:"
docker exec airflow bash -c 'echo "  DEMO_MODE=$DEMO_MODE"; echo "  DEMO_THRESHOLD_MB=$DEMO_THRESHOLD_MB MB"; echo "  ARCHIVE_THRESHOLD_MB=$ARCHIVE_THRESHOLD_MB MB"'

echo ""
echo "🔍 To verify in Airflow logs:"
echo "  docker logs airflow 2>&1 | grep MODE"
echo ""
echo "✅ Done!"

