'''
Usage example
python3 /home/hylmarj/hyl-amplify-logs/src/local/action_amplify_log_analysis.py

Example output
Log Analysis Summary
--------------------------------------------------
Date range: 2023-10-01 to 2024-12-08
Total calendar days: 435
Days with logs: 435
Days without logs: 0

Traffic Analysis
--------------------------------------------------
Total requests: 554,769
Human requests: 57,808 (10.4%)
Bot requests: 496,961 (89.6%)

IP Analysis
--------------------------------------------------
Total unique IPs: 27,389
Unique human IPs: 10,076
Unique bot IPs: 21,494

Daily Averages (for days with logs)
--------------------------------------------------
Average total requests: 1275.3
Average human requests: 132.9
Average bot requests: 1142.4
Average unique human IPs: 43.9
Average unique bot IPs: 95.6

Plot saved as 'log_analysis.png'
Detailed data saved to '/home/hylmarj/_scratch/app=danse_tech/type=amplify_logs_analysis/log_analysis.csv'
'''

import os
from pathlib import Path
import json
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import re

def get_calendar_dates():
    """Generate all dates from start to end of the expected range"""
    start_date = datetime(2024, 10, 1)
    end_date = datetime(2025, 3, 26)
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    return dates

def parse_log_file(file_path):
    """Process a single log file and return daily counts and IP information"""
    daily_counts = defaultdict(lambda: {'total': 0, 'human': 0, 'bot': 0})
    status_counts = defaultdict(int)
    result_types = defaultdict(int)
    daily_ips = defaultdict(lambda: {'total': set(), 'human': set(), 'bot': set()})
    
    ip_activity = defaultdict(lambda: {
        'timestamps': [],
        'paths': [],
        'user_agents': set(),
        'edge_locations': set(),
        'status_codes': [],
        'protocols': set(),
    })
    
    try:
        with open(file_path, 'r') as f:
            # Skip empty or invalid files
            if not f.readable():
                return daily_counts, status_counts, result_types, daily_ips, ip_activity
                
            # Read and process header
            header_line = f.readline().strip()
            if not header_line:
                return daily_counts, status_counts, result_types, daily_ips, ip_activity
                
            headers = header_line.split(',')
            
            # Process each line
            for line in f:
                try:
                    # Split line and cleanup
                    fields = line.strip().split(',')
                    if len(fields) != len(headers):
                        continue
                    
                    # Create clean row dict
                    row = {h.strip('"'): v.strip('"') for h, v in zip(headers, fields)}
                    
                    # Extract key fields
                    date = row['date']
                    c_ip = row['c-ip']
                    timestamp = f"{date} {row['time']}"
                    
                    # Update IP activity with proper error handling
                    try:
                        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        ip_activity[c_ip]['timestamps'].append(dt)
                        ip_activity[c_ip]['paths'].append(row['cs-uri-stem'])
                        ip_activity[c_ip]['user_agents'].add(row.get('cs(User-Agent)', '-'))
                        ip_activity[c_ip]['edge_locations'].add(row.get('x-edge-location', '-'))
                        ip_activity[c_ip]['status_codes'].append(row.get('sc-status', ''))
                        ip_activity[c_ip]['protocols'].add(row.get('cs-protocol', '-'))
                    except ValueError:
                        continue
                    
                    # Bot detection with proper type handling
                    is_bot = detect_bot_patterns(row, ip_activity[c_ip])
                    
                    # Update metrics
                    daily_counts[date]['total'] += 1
                    daily_counts[date]['bot' if is_bot else 'human'] += 1
                    
                    daily_ips[date]['total'].add(c_ip)
                    daily_ips[date]['bot' if is_bot else 'human'].add(c_ip)
                    
                    status_counts[row.get('sc-status', '')] += 1
                    result_types[row.get('x-edge-result-type', '')] += 1
                    
                except Exception as e:
                    continue
                    
        return daily_counts, status_counts, result_types, daily_ips, ip_activity
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return daily_counts, status_counts, result_types, daily_ips, ip_activity


def detect_bot_patterns(row, ip_history):
    """Enhanced bot detection using temporal and behavioral patterns."""
    # Basic bot patterns check
    try:
        if is_likely_bot(row):
            return True
    except:
        pass
    
    # Time-based patterns
    if ip_history['timestamps']:
        try:
            # Get requests in last minute
            latest = max(ip_history['timestamps'])
            recent = [t for t in ip_history['timestamps'] 
                     if (latest - t).total_seconds() <= 60]
            
            if len(recent) > 30:  # More than 30 requests per minute
                return True
        except:
            pass
    
    # Behavioral patterns
    try:
        # Multiple user agents
        if len(ip_history['user_agents']) > 2:
            return True
            
        # Geographic spread
        if len(ip_history['edge_locations']) > 3:
            return True
            
        # Protocol switching
        if len(ip_history['protocols']) > 2:
            return True
            
        # Error patterns
        recent_errors = [s for s in ip_history['status_codes'][-10:]
                        if s in ['404', '403', '400', '500']]
        if len(recent_errors) >= 3:
            return True
            
        # Path scanning
        if len(ip_history['paths']) >= 3:
            recent = ip_history['paths'][-3:]
            if any(p1[:-1] == p2[:-1] and p1[-1].isdigit() and p2[-1].isdigit()
                   for p1, p2 in zip(recent, recent[1:])):
                return True
    except:
        pass
    
    return False

def is_likely_bot(row):
    """Determine if a log entry is likely from a bot based on basic patterns"""
    try:
        user_agent = str(row.get('cs(User-Agent)', '')).lower()
        uri_stem = str(row.get('cs-uri-stem', '')).lower()
        referer = str(row.get('cs(Referer)', '')).lower()
        method = str(row.get('cs-method', '')).upper()
        status = str(row.get('sc-status', ''))
        
        bot_patterns = [
            r'bot', r'crawler', r'spider', r'ahref', r'scan',
            r'monitoring', r'http', r'python', r'check', r'probe'
        ]
        
        return (
            any(pattern in user_agent for pattern in bot_patterns) or
            any(p in uri_stem for p in ['robots.txt', '.env', 'wp-login', 'favicon.ico']) or
            method == 'HEAD' or
            status in ['404', '403', '400'] or
            (referer == '-' and uri_stem != '/') or
            bool(re.search(r'http://\d+\.\d+\.\d+\.\d+', referer))
        )
    except:
        return False
    

def analyze_logs(base_path):
    """Analyze all log files and compare with calendar dates"""
    base_dir = Path(base_path)
    calendar_dates = get_calendar_dates()
    
    all_counts = defaultdict(lambda: {'total': 0, 'human': 0, 'bot': 0})
    total_status_counts = defaultdict(int)
    total_result_types = defaultdict(int)
    all_daily_ips = defaultdict(lambda: {'total': set(), 'human': set(), 'bot': set()})
    
    # Track global IP activity
    global_ip_activity = defaultdict(lambda: {
        'timestamps': [],
        'paths': [],
        'user_agents': set(),
        'edge_locations': set(),
        'status_codes': [],
        'protocols': set(),
    })
    
    print("\nProcessing log files:")
    for date_dir in base_dir.glob("date_export=*"):
        log_files = list(date_dir.glob("log_*"))
        if log_files:
            log_file = log_files[0]
            print(f"Processing: {log_file}")
            daily_counts, status_counts, result_types, daily_ips, ip_activity = parse_log_file(log_file)
            
            # Merge IP activity data
            for ip, activity in ip_activity.items():
                global_ip_activity[ip]['timestamps'].extend(activity['timestamps'])
                global_ip_activity[ip]['paths'].extend(activity['paths'])
                global_ip_activity[ip]['user_agents'].update(activity['user_agents'])
                global_ip_activity[ip]['edge_locations'].update(activity['edge_locations'])
                global_ip_activity[ip]['status_codes'].extend(activity['status_codes'])
                global_ip_activity[ip]['protocols'].update(activity['protocols'])
            
            # Aggregate other counts
            for date, counts in daily_counts.items():
                all_counts[date]['total'] += counts['total']
                all_counts[date]['human'] += counts['human']
                all_counts[date]['bot'] += counts['bot']
                all_daily_ips[date]['total'].update(daily_ips[date]['total'])
                all_daily_ips[date]['human'].update(daily_ips[date]['human'])
                all_daily_ips[date]['bot'].update(daily_ips[date]['bot'])
            
            for status, count in status_counts.items():
                total_status_counts[status] += count
            for result, count in result_types.items():
                total_result_types[result] += count
    
    # Create DataFrame with enhanced metrics
    df = create_analysis_dataframe(calendar_dates, all_counts, all_daily_ips, global_ip_activity)
    
    # Return only what's needed for the main analysis
    return df, total_status_counts, total_result_types

def create_analysis_dataframe(calendar_dates, all_counts, all_daily_ips, global_ip_activity):
    """Create enhanced DataFrame with additional metrics"""
    df = pd.DataFrame({'date': calendar_dates})
    
    # Basic metrics
    for traffic_type in ['total', 'human', 'bot']:
        df[f'{traffic_type}_count'] = df['date'].map(lambda x: all_counts[x][traffic_type])
        df[f'{traffic_type}_count'] = df[f'{traffic_type}_count'].fillna(0).astype(int)
        df[f'{traffic_type}_unique_ips'] = df['date'].map(lambda x: len(all_daily_ips[x][traffic_type]))
    
    # Enhanced metrics using global_ip_activity
    df['avg_requests_per_ip'] = df.apply(
        lambda row: row['total_count'] / max(1, row['total_unique_ips']), axis=1
    )
    
    # Create daily metrics for global IP activity
    df['multi_agent_ips'] = df['date'].map(
        lambda d: sum(1 for ip, data in global_ip_activity.items() 
                     if len(data['user_agents']) > 1)
    )
    
    df['multi_location_ips'] = df['date'].map(
        lambda d: sum(1 for ip, data in global_ip_activity.items() 
                     if len(data['edge_locations']) > 1)
    )
    
    # Calculate cumulative metrics
    for traffic_type in ['total', 'human', 'bot']:
        cumulative_ips = []
        current_ips = set()
        for date in df['date']:
            current_ips.update(all_daily_ips[date][traffic_type])
            cumulative_ips.append(len(current_ips))
        df[f'cumulative_{traffic_type}_ips'] = cumulative_ips
    
    df['has_logs'] = df['total_count'] > 0
    df['date'] = pd.to_datetime(df['date'])
    
    return df

def plot_daily_logs(df):
    """Create visualizations for the log data including human/bot separation"""
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 18))
    
    dates = df['date'].to_numpy()
    has_logs = df['has_logs'].to_numpy()
    
    # Convert series to numpy arrays for plotting
    total_count = df['total_count'].to_numpy()
    human_count = df['human_count'].to_numpy()
    bot_count = df['bot_count'].to_numpy()
    human_ips = df['human_unique_ips'].to_numpy()
    bot_ips = df['bot_unique_ips'].to_numpy()
    cumul_human = df['cumulative_human_ips'].to_numpy()
    cumul_bot = df['cumulative_bot_ips'].to_numpy()
    
    # Total traffic plot
    ax1.plot(dates, total_count, 'b-', linewidth=1, label='Total Traffic')
    if np.any(~has_logs):
        ax1.fill_between(dates, 0, np.max(total_count),
                        where=~has_logs,
                        color='red', alpha=0.1,
                        label='Missing Logs')
    ax1.set_title('Daily Total Log Counts\n(Red background indicates missing logs)')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Number of Logs')
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
    ax1.legend()
    
    # Human vs Bot traffic plot
    ax2.plot(dates, human_count, 'g-', label='Human Traffic')
    ax2.plot(dates, bot_count, 'r-', label='Bot Traffic')
    ax2.set_title('Human vs Bot Traffic')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Number of Requests')
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
    ax2.legend()
    
    # Unique IPs plot
    ax3.plot(dates, human_ips, 'g-', label='Daily Human IPs')
    ax3.plot(dates, bot_ips, 'r-', label='Daily Bot IPs')
    ax3.plot(dates, cumul_human, 'g--', label='Cumulative Human IPs')
    ax3.plot(dates, cumul_bot, 'r--', label='Cumulative Bot IPs')
    ax3.set_title('IP Address Analysis (Human vs Bot)')
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Number of Unique IPs')
    ax3.grid(True, linestyle='--', alpha=0.7)
    ax3.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
    ax3.legend()
    
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig('/home/hylmarj/_scratch/app=danse_tech/type=amplify_logs_analysis/log_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()

def print_traffic_stats(df):
    """Print traffic statistics with safe percentage calculations"""
    total_requests = df['total_count'].sum()
    human_requests = df['human_count'].sum()
    bot_requests = df['bot_count'].sum()
    
    print("\nTraffic Analysis")
    print("-" * 50)
    print(f"Total requests: {total_requests:,}")
    
    if total_requests > 0:
        human_pct = (human_requests / total_requests * 100) if total_requests > 0 else 0
        bot_pct = (bot_requests / total_requests * 100) if total_requests > 0 else 0
        print(f"Human requests: {human_requests:,} ({human_pct:.1f}%)")
        print(f"Bot requests: {bot_requests:,} ({bot_pct:.1f}%)")
    else:
        print("No requests found in logs")

def main():
    base_path = "/home/hylmarj/_scratch/app=danse_tech/type=amplify_logs"
    
    if not Path(base_path).exists():
        print(f"Error: Path {base_path} does not exist")
        return
        
    print("Starting log analysis...")
    df, status_counts, result_types = analyze_logs(base_path)  # Now only unpacks 3 values
    
    # Analysis Summary
    print("\nLog Analysis Summary")
    print("-" * 50)
    print(f"Date range: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"Total calendar days: {len(df)}")
    print(f"Days with logs: {df['has_logs'].sum()}")
    print(f"Days without logs: {len(df) - df['has_logs'].sum()}")
    
    # Print traffic stats
    print_traffic_stats(df)
    
    # IP Analysis
    total_unique = df['cumulative_total_ips'].max()
    if total_unique > 0:
        print("\nIP Analysis")
        print("-" * 50)
        print(f"Total unique IPs: {total_unique:,}")
        print(f"Unique human IPs: {df['cumulative_human_ips'].max():,}")
        print(f"Unique bot IPs: {df['cumulative_bot_ips'].max():,}")
    
        # Daily Averages (for days with logs)
        logs_present = df[df['has_logs']]
        if not logs_present.empty:
            print("\nDaily Averages (for days with logs)")
            print("-" * 50)
            print(f"Average total requests: {logs_present['total_count'].mean():.1f}")
            print(f"Average human requests: {logs_present['human_count'].mean():.1f}")
            print(f"Average bot requests: {logs_present['bot_count'].mean():.1f}")
            print(f"Average unique human IPs: {logs_present['human_unique_ips'].mean():.1f}")
            print(f"Average unique bot IPs: {logs_present['bot_unique_ips'].mean():.1f}")
    
    # Missing dates (only show if there are some logs)
    if df['has_logs'].any():
        missing_dates = df[~df['has_logs']]['date'].dt.strftime('%Y-%m-%d').tolist()
        if missing_dates:
            print("\nDates without logs:")
            for date in sorted(missing_dates):
                print(f"- {date}")
    
    # Create visualization and save data
    if df['has_logs'].any():
        try:
            plot_daily_logs(df)
            print("\nPlot saved as '/home/hylmarj/_scratch/app=danse_tech/type=amplify_logs_analysis/log_analysis.png'")
        except Exception as e:
            print(f"\nError during plotting: {str(e)}")
            import traceback
            traceback.print_exc()
    
        # Save detailed data
        df.to_csv('/home/hylmarj/_scratch/app=danse_tech/type=amplify_logs_analysis/log_analysis.csv', index=False)
        print("Detailed data saved to '/home/hylmarj/_scratch/app=danse_tech/type=amplify_logs_analysis/log_analysis.csv'")
    else:
        print("\nNo log data found to plot or save")

if __name__ == "__main__":
    main()