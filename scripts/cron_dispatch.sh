#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Evaluates local Sydney time and triggers Morning or Afternoon brief.
# Self-adjusts for Daylight Saving Time (AEST/AEDT) and Day-of-Week.

WORKSPACE="/usr/local/google/home/rsibo/sandbox/daily-brief"
UV_BIN="/usr/local/google/home/rsibo/.local/bin/uv"

SYDNEY_HOUR=$(TZ="Australia/Sydney" date +%H)
SYDNEY_DOW=$(TZ="Australia/Sydney" date +%u) # 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun

# 1. MORNING BRIEF: Runs 06:00 AM Sydney, Monday through Saturday (DOW 1-6)
if [ "$SYDNEY_HOUR" -eq 6 ] && [ "$SYDNEY_DOW" -le 6 ]; then
    echo "[$(date -Iseconds)] Triggering Morning Brief (Sydney Hour: $SYDNEY_HOUR, DOW: $SYDNEY_DOW)" >> /tmp/daily_brief_cron.log
    cd "$WORKSPACE" && "$UV_BIN" run python scripts/run_daily_brief.py --mode morning >> /tmp/daily_brief_morning.log 2>&1
fi

# 2. AFTERNOON BRIEF: Runs 04:00 PM (16:00) Sydney, Monday through Friday (DOW 1-5)
if [ "$SYDNEY_HOUR" -eq 16 ] && [ "$SYDNEY_DOW" -le 5 ]; then
    echo "[$(date -Iseconds)] Triggering Afternoon Brief (Sydney Hour: $SYDNEY_HOUR, DOW: $SYDNEY_DOW)" >> /tmp/daily_brief_cron.log
    cd "$WORKSPACE" && "$UV_BIN" run python scripts/run_daily_brief.py --mode afternoon >> /tmp/daily_brief_afternoon.log 2>&1
fi
