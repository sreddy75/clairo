#!/bin/zsh

# Load .zshrc to get aliases
source ~/.zshrc

sleep_with_countdown() {
    local seconds=$1
    while [ $seconds -gt 0 ]; do
        printf "\rSleeping for %02d:%02d..." $((seconds/60)) $((seconds%60))
        sleep 1
        seconds=$((seconds - 1))
    done
    printf "\rSleeping complete.           \n"
}

parse_and_display_json() {
    local json_line="$1"

    # Extract message type
    local msg_type=$(echo "$json_line" | jq -r '.type // "unknown"' 2>/dev/null)

    if [ "$msg_type" = "assistant" ]; then
        # Extract tokens and model info
        local model=$(echo "$json_line" | jq -r '.message.model // "unknown"' 2>/dev/null)
        local input_tokens=$(echo "$json_line" | jq -r '.message.usage.input_tokens // 0' 2>/dev/null)
        local output_tokens=$(echo "$json_line" | jq -r '.message.usage.output_tokens // 0' 2>/dev/null)
        local cache_tokens=$(echo "$json_line" | jq -r '.message.usage.cache_read_input_tokens // 0' 2>/dev/null)

        # Extract content
        local content=$(echo "$json_line" | jq -r '.message.content[]? | if .type == "text" then .text elif .type == "tool_use" then "🔧 Tool: \(.name) - \(.input | tostring)" else empty end' 2>/dev/null)

        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🤖 ASSISTANT | Model: $model | In: $input_tokens | Out: $output_tokens | Cache: $cache_tokens"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        if [ -n "$content" ] && [ "$content" != "null" ]; then
            echo "$content"
        fi
        echo ""

    elif [ "$msg_type" = "user" ]; then
        local content=$(echo "$json_line" | jq -r '.message.content[]? | if .type == "tool_result" then "📄 Tool Result: \(.content | tostring)" else .text // empty end' 2>/dev/null)

        echo "👤 USER"
        echo "────────────────────────────────────────────────────────────────────────────"
        if [ -n "$content" ] && [ "$content" != "null" ]; then
            echo "$content" | head -5  # Limit tool results to first 5 lines
            if [ $(echo "$content" | wc -l) -gt 5 ]; then
                echo "... (truncated)"
            fi
        fi
        echo ""

    elif [ "$msg_type" = "result" ]; then
        local subtype=$(echo "$json_line" | jq -r '.subtype // "unknown"' 2>/dev/null)
        local duration=$(echo "$json_line" | jq -r '.duration_ms // 0' 2>/dev/null)
        local turns=$(echo "$json_line" | jq -r '.num_turns // 0' 2>/dev/null)

        echo "🎯 RESULT | Status: $subtype | Duration: ${duration}ms | Turns: $turns"
        echo "════════════════════════════════════════════════════════════════════════════"
        echo ""
    fi
}

run_claude_with_parsing() {
    local cmd="$1"

    # Pipe command output directly through parser and save to file for rate limit detection
    eval "$cmd" | tee ./../.claude/last_output.log | while IFS= read -r line; do
        parse_and_display_json "$line"
    done
}

while true; do
    echo "🚀 Starting Claude session..."
    source ~/.zshrc
    run_claude_with_parsing "cat ./../.claude/prompt | cdd --verbose --output-format stream-json"

    # Check for rate limits in the saved output
    if grep -q "5-hour limit reached ∙ resets" ./../.claude/last_output.log; then
        echo "⚠️  Rate limit detected, extracting reset time..."

        reset_time=$(grep -o "resets [0-9]\{1,2\}[ap]m" ./../.claude/last_output.log | sed 's/resets //')

        if [ -n "$reset_time" ]; then
            echo "🕐 Found reset time: $reset_time"

            hour=$(echo "$reset_time" | sed 's/[ap]m//')
            period=$(echo "$reset_time" | grep -o "[ap]m")

            if [ "$period" = "pm" ] && [ "$hour" != "12" ]; then
                hour=$((hour + 12))
            elif [ "$period" = "am" ] && [ "$hour" = "12" ]; then
                hour=0
            fi

            current_time=$(date +%s)
            today_reset=$(date -j -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) ${hour}:00:00" +%s 2>/dev/null)

            if [ $current_time -gt $today_reset ]; then
                tomorrow_reset=$(date -j -f "%Y-%m-%d %H:%M:%S" "$(date -v+1d +%Y-%m-%d) ${hour}:00:00" +%s)
                sleep_duration=$((tomorrow_reset - current_time))
                reset_description="tomorrow at $reset_time"
            else
                sleep_duration=$((today_reset - current_time))
                reset_description="today at $reset_time"
            fi

            sleep_duration=$((sleep_duration + 60))

            echo "🔄 Switching to DeepSeek API until Claude reset ($reset_description)..."

            end_time=$((current_time + sleep_duration))
            while [ $(date +%s) -lt $end_time ]; do
                run_claude_with_parsing "ANTHROPIC_BASE_URL='https://api.deepseek.com/anthropic' ANTHROPIC_AUTH_TOKEN='$DEEPSEEK_API_KEY' ANTHROPIC_MODEL='deepseek-chat' ANTHROPIC_SMALL_FAST_MODEL='deepseek-chat' claude -p --dangerously-skip-permissions --verbose --output-format stream-json < ./../.claude/prompt"
                sleep_with_countdown 900
            done

            echo "✅ Claude cooldown over, switching back."
        else
            echo "❌ Could not extract reset time, defaulting to 1 hour DeepSeek fallback..."
            end_time=$(( $(date +%s) + 3600 ))
            while [ $(date +%s) -lt $end_time ]; do
                run_claude_with_parsing "ANTHROPIC_BASE_URL='https://api.deepseek.com/anthropic' ANTHROPIC_AUTH_TOKEN='$DEEPSEEK_API_KEY' ANTHROPIC_MODEL='deepseek-chat' ANTHROPIC_SMALL_FAST_MODEL='deepseek-chat' claude -p --dangerously-skip-permissions --verbose --output-format stream-json < ./../.claude/prompt"
                sleep_with_countdown 900
            done
        fi
    else
        echo "💤 Normal execution, sleeping for 1 minutes..."
        sleep_with_countdown 60
    fi
done
