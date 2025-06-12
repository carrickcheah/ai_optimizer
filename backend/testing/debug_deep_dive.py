#!/usr/bin/env python3

import sys
import os
import logging
from datetime import datetime

# --- Robust Path Correction ---
def find_backend_dir(start_path):
    path = os.path.abspath(start_path)
    while True:
        # We are looking for the 'ai_optimizer' directory, which is the project root
        if os.path.basename(path) == 'ai_optimizer':
            backend_dir = os.path.join(path, 'backend')
            if os.path.isdir(backend_dir):
                return backend_dir
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent

script_dir = os.path.dirname(__file__)
backend_path = find_backend_dir(script_dir)

if backend_path and backend_path not in sys.path:
    sys.path.insert(0, backend_path)
else:
    # As a fallback for different structures, just add the parent of 'backend'
    # This handles running from within 'ai_optimizer/backend'
    potential_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    if os.path.basename(potential_root) == 'ai_optimizer':
         if os.path.join(potential_root, 'backend') not in sys.path:
            sys.path.insert(0, os.path.join(potential_root, 'backend'))

# Correct import from the actual data ingestion module
from app.data_ingestion.mariadb_parser import load_jobs_planning_data
from app.scheduling.greedy_solver import GreedyScheduler, GreedyConfigManager
from app.utils.time_utils import epoch_to_datetime

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s'
)
logger = logging.getLogger(__name__)

def debug_joaw25060047_failure():
    """Debugs why job JOAW25060047_CD11-026C-1/2 fails to schedule."""
    
    job_id_to_debug = "JOAW25060047_CD11-026C-1/2"
    machine_id_to_debug = "WS01"
    
    logger.info(f"--- Starting Deep Dive for Job: {job_id_to_debug} on Machine: {machine_id_to_debug} ---")

    try:
        # 1. Load all data using the correct function
        logger.info("Loading production data using 'load_jobs_planning_data'...")
        all_jobs, all_machines, _ = load_jobs_planning_data()
        
        if not all_jobs:
            logger.error("No jobs loaded. Aborting debug.")
            return

        # Pre-process jobs to ensure 'processing_time' key exists, as requested
        for job in all_jobs:
            if 'processing_time' not in job:
                job['processing_time'] = 0.0
                logger.warning(f"Patched Job {job.get('job_id', 'Unknown')}: missing 'processing_time', defaulted to 0.")

        # 2. Find the specific job
        target_job = next((j for j in all_jobs if j['job_id'] == job_id_to_debug), None)
        if not target_job:
            logger.error(f"Could not find job '{job_id_to_debug}' in loaded data.")
            return

        logger.info(f"Found Job: {target_job['job_id']}")
        logger.info(f"  - Target Date (LCD): {target_job.get('lcd_date_str')}")
        logger.info(f"  - Material Arrival: {target_job.get('material_arrival_str')}")
        
        # Use the 'processing_time' field which is already in seconds
        processing_time_seconds = target_job.get('processing_time', 0)
        setup_time_seconds = target_job.get('setting_hours', 0) * 3600 # setting_hours is in hours
        total_required_time = processing_time_seconds + setup_time_seconds

        logger.info(f"  - Processing Time: {processing_time_seconds / 3600:.2f} hours")
        logger.info(f"  - Setup Time: {setup_time_seconds / 3600:.2f} hours")
        logger.info(f"  - Total Required Time (incl. setup): {total_required_time / 3600:.2f} hours")

        # 3. Load config and initialize the scheduler correctly
        logger.info("Loading config and initializing the Greedy Scheduler...")
        config = GreedyConfigManager.load_config()
        scheduler = GreedyScheduler(config)

        # 4. Run the full scheduler to get the machine state
        logger.info("Running the full scheduler to populate machine calendars...")
        # The `run` method in the original script seems to be a wrapper. 
        # The actual scheduling logic is in `schedule_jobs`.
        final_schedule = scheduler.schedule_jobs(all_jobs, [m['MachineName_v'] for m in all_machines])

        # 5. Get the state of the target machine from the final schedule
        logger.info(f"Inspecting final calendar for machine '{machine_id_to_debug}'...")
        machine_schedule = final_schedule.get(machine_id_to_debug, [])
            
        logger.info(f"Final state of '{machine_id_to_debug}' calendar:")
        if not machine_schedule:
            logger.info("  - Machine calendar is empty or job was not scheduled on it.")
        else:
            for i, scheduled_job_tuple in enumerate(sorted(machine_schedule, key=lambda x: x[1])):
                try:
                    # Correctly unpack the 5-item tuple from the scheduler
                    job_id, start_epoch, end_epoch, _priority, _details = scheduled_job_tuple
                    
                    logger.info(f"  - Slot {i+1}: Job {job_id}")
                    logger.info(f"    - Start: {epoch_to_datetime(start_epoch)}")
                    logger.info(f"    - End:   {epoch_to_datetime(end_epoch)}")
                except ValueError:
                    logger.error(f"Could not unpack tuple: {scheduled_job_tuple}. It has {len(scheduled_job_tuple)} items.")
                    logger.info(f"  - Slot {i+1}: Raw Data {scheduled_job_tuple}")
        
        # 6. Analyze the gaps
        logger.info(f"Analyzing calendar gaps for a {total_required_time / 3600:.2f}hr slot...")
        
        now_epoch = int(datetime.now().timestamp())
        deadline_epoch = target_job.get('lcd_date_epoch', now_epoch + 3600 * 24 * 30)
        
        found_slot = False
        last_end_time = now_epoch
        
        sorted_schedule = sorted(machine_schedule, key=lambda x: x[1])

        # Check gap before first job
        first_start = sorted_schedule[0][1] if sorted_schedule else deadline_epoch
        if first_start - last_end_time >= total_required_time:
            logger.info(f"Found a potential slot at the beginning of the calendar ({ (first_start - last_end_time)/3600:.2f} hrs).")
            found_slot = True
        
        if not found_slot:
            for i, scheduled_job_tuple in enumerate(sorted_schedule):
                job_id, start_epoch, end_epoch = scheduled_job_tuple
                gap_start = last_end_time
                gap_end = start_epoch
                gap_duration = gap_end - gap_start
                
                logger.debug(f"Checking gap before job {job_id}: from {epoch_to_datetime(gap_start)} to {epoch_to_datetime(gap_end)} ({gap_duration/3600:.2f} hrs)")
                if gap_duration >= total_required_time:
                    logger.info(f"Found a potential {gap_duration/3600:.2f}hr slot before job {job_id}. This should be enough.")
                    found_slot = True
                    break
                last_end_time = end_epoch

        if not found_slot and sorted_schedule:
             last_job_end_time = sorted_schedule[-1][2]
             gap_duration = deadline_epoch - last_job_end_time
             logger.debug(f"Checking gap at the end of calendar: from {epoch_to_datetime(last_job_end_time)} to {epoch_to_datetime(deadline_epoch)} ({gap_duration/3600:.2f} hrs)")
             if gap_duration >= total_required_time:
                 logger.info(f"Found potential slot at the end of the calendar.")
                 found_slot = True
        
        # Check if our target job was actually scheduled
        job_was_scheduled = any(s_job[0] == job_id_to_debug for s_job in machine_schedule)

        if job_was_scheduled:
            logger.info("🎉 SUCCESS: The job WAS scheduled on this machine. The 'unscheduled' warning must be for a different reason or from a different run.")
        elif found_slot:
            logger.info("CONCLUSION: A sufficient time slot EXISTS on the calendar.")
            logger.error("REAL ISSUE: The scheduling failure is due to a LOGIC FLAW. The simple gap check found a spot, but the scheduler's complex logic is failing. This often happens with how the scheduler handles jobs that span multiple days, especially over weekends or non-working hours. It might be calculating the 'end time' incorrectly when it crosses a day boundary and then failing a deadline check.")
        else:
            logger.info("CONCLUSION: No single continuous slot of {total_required_time / 3600:.2f} hours exists.")
            logger.error("REAL ISSUE: The machine is fully booked with higher priority jobs. The unscheduled warning is correct because there is no available capacity.")

    except Exception as e:
        logger.critical(f"An unexpected error occurred during the debug script: {e}", exc_info=True)

if __name__ == "__main__":
    # Activate venv and run
    # source /Users/carrickcheah/llms_project/services/ai_optimizer/.venv/bin/activate && python debug_deep_dive.py
    debug_joaw25060047_failure() 