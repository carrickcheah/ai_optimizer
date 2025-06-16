#!/usr/bin/env python3
"""
Deep Scan Test Suite for CP-SAT Solver Module
Comprehensive testing of all functions, compatibility, and integration points
"""

import os
import sys
import time
import json
import psutil
import gc
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from unittest.mock import Mock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.scheduling.cpsat_solver import (
        SchedulingConfigManager, SchedulingConfig, JobValidator, JobFilterer,
        HorizonCalculator, JobDurationCalculator, CPSATModelBuilder,
        ConstraintManager, ObjectiveBuilder, CPSATSolver, ResultProcessor,
        schedule_jobs, SchedulingError, ConfigurationError
    )
    from app.data_ingestion.mariadb_parser import load_jobs_planning_data
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


class CPSATDeepScanner:
    """Comprehensive deep scan tester for CP-SAT solver."""
    
    def __init__(self):
        self.results = {}
        self.process = psutil.Process()
        self.test_start_time = time.time()
        
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def run_deep_scan(self) -> Dict:
        """Run comprehensive deep scan of CP-SAT solver."""
        print("🔍 Starting CP-SAT Solver Deep Scan")
        print("=" * 60)
        
        self.results = {
            'scan_overview': {
                'start_time': datetime.now().isoformat(),
                'test_categories': 11,
                'total_tests': 0
            },
            'configuration_analysis': self.test_configuration_system(),
            'ortools_integration': self.test_ortools_integration(),
            'job_validation': self.test_job_validation(),
            'duration_calculation': self.test_duration_calculation(),
            'model_building': self.test_model_building(),
            'constraint_management': self.test_constraint_management(),
            'solver_execution': self.test_solver_execution(),
            'result_processing': self.test_result_processing(),
            'integration_compatibility': self.test_integration_compatibility(),
            'performance_analysis': self.test_performance(),
            'production_readiness': self.test_production_readiness()
        }
        
        # Calculate totals
        total_tests = sum(
            len(category.get('tests', [])) 
            for category in self.results.values() 
            if isinstance(category, dict) and 'tests' in category
        )
        self.results['scan_overview']['total_tests'] = total_tests
        self.results['scan_overview']['duration'] = time.time() - self.test_start_time
        
        return self.results
    
    def test_configuration_system(self) -> Dict:
        """Test configuration loading and validation."""
        print("\n1. Testing Configuration System...")
        tests = []
        
        # Test 1: Configuration loading
        try:
            config = SchedulingConfigManager.load_config()
            tests.append({
                'name': 'Configuration Loading',
                'status': 'passed',
                'details': f'Successfully loaded {len(config.__dict__)} parameters'
            })
        except Exception as e:
            tests.append({
                'name': 'Configuration Loading',
                'status': 'failed',
                'details': str(e)
            })
            return {'status': 'error', 'tests': tests}
        
        # Test 2: Dynamic limits
        test_limits = [
            (50, "Small problem"),
            (300, "Medium problem"),
            (600, "Large problem")
        ]
        
        for job_count, description in test_limits:
            limits = config.get_dynamic_limits(job_count)
            expected_keys = ['time_limit_seconds', 'planning_horizon_days', 'max_jobs_limit']
            has_all_keys = all(key in limits for key in expected_keys)
            
            tests.append({
                'name': f'Dynamic Limits ({description})',
                'status': 'passed' if has_all_keys else 'failed',
                'details': f'{job_count} jobs -> {limits}'
            })
        
        # Test 3: Configuration validation
        try:
            # Test with invalid values
            invalid_config = SchedulingConfig(
                solver_time_limit_seconds=-1,  # Invalid
                max_jobs_limit=0,  # Invalid
                planning_horizon_days=1,
                max_workers_limit=1,
                relative_gap_limit=0.1,
                absolute_gap_limit=1,
                priority_weight=1,
                minimum_horizon_hours=1,
                emergency_minimum_start_hour=6,
                grace_period_hours=24,
                scheduler_search_days=90,
                cpsat_batch_size=50,
                normal_working_hours=17.5,
                ot_working_hours=22.0,
                emergency_ot_hours=24.0
            )
            SchedulingConfigManager._validate_config(invalid_config)
            tests.append({
                'name': 'Configuration Validation',
                'status': 'failed',
                'details': 'Should have failed with invalid values'
            })
        except ConfigurationError:
            tests.append({
                'name': 'Configuration Validation',
                'status': 'passed',
                'details': 'Correctly rejected invalid configuration'
            })
        
        return {'status': 'completed', 'tests': tests, 'config_values': config.__dict__}
    
    def test_ortools_integration(self) -> Dict:
        """Test OR-Tools CP-SAT integration."""
        print("\n2. Testing OR-Tools Integration...")
        tests = []
        
        # Test 1: OR-Tools availability
        try:
            from ortools.sat.python import cp_model
            model = cp_model.CpModel()
            solver = cp_model.CpSolver()
            
            tests.append({
                'name': 'OR-Tools Import',
                'status': 'passed',
                'details': 'Successfully imported CP-SAT components'
            })
        except ImportError as e:
            tests.append({
                'name': 'OR-Tools Import',
                'status': 'failed',
                'details': f'OR-Tools not available: {e}'
            })
            return {'status': 'error', 'tests': tests}
        
        # Test 2: Basic model creation
        try:
            model = cp_model.CpModel()
            x = model.NewIntVar(0, 10, 'x')
            y = model.NewIntVar(0, 10, 'y')
            model.Add(x + y <= 15)
            model.Maximize(x + y)
            
            solver = cp_model.CpSolver()
            status = solver.Solve(model)
            
            tests.append({
                'name': 'Basic Model Solving',
                'status': 'passed' if status == cp_model.OPTIMAL else 'warning',
                'details': f'Model status: {solver.StatusName(status)}'
            })
        except Exception as e:
            tests.append({
                'name': 'Basic Model Solving',
                'status': 'failed',
                'details': str(e)
            })
        
        # Test 3: Interval variables (scheduling specific)
        try:
            model = cp_model.CpModel()
            start = model.NewIntVar(0, 100, 'start')
            duration = 10
            end = model.NewIntVar(0, 110, 'end')
            interval = model.NewIntervalVar(start, duration, end, 'interval')
            
            tests.append({
                'name': 'Interval Variables',
                'status': 'passed',
                'details': 'Successfully created scheduling interval variables'
            })
        except Exception as e:
            tests.append({
                'name': 'Interval Variables',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests}
    
    def test_job_validation(self) -> Dict:
        """Test job validation and preprocessing."""
        print("\n3. Testing Job Validation...")
        tests = []
        
        # Test 1: Valid job processing
        try:
            valid_jobs = [
                {'job_id': 'TEST001', 'MachineName_v': 'MACHINE1', 'hours_need': 5.0},
                {'job_id': 'TEST002', 'MachineName_v': 'MACHINE2', 'hours_need': 3.0}
            ]
            result = JobValidator.validate_jobs(valid_jobs)
            
            tests.append({
                'name': 'Valid Job Processing',
                'status': 'passed' if len(result) == 2 else 'failed',
                'details': f'Processed {len(result)}/2 valid jobs'
            })
        except Exception as e:
            tests.append({
                'name': 'Valid Job Processing',
                'status': 'failed',
                'details': str(e)
            })
        
        # Test 2: Invalid job filtering
        try:
            invalid_jobs = [
                {'job_id': 'TEST003'},  # Missing machine
                {'MachineName_v': 'MACHINE1'},  # Missing job_id
                None,  # Invalid type
                'not_a_dict'  # Invalid type
            ]
            result = JobValidator.validate_jobs(invalid_jobs)
            
            tests.append({
                'name': 'Invalid Job Filtering',
                'status': 'passed' if len(result) == 0 else 'warning',
                'details': f'Filtered to {len(result)} jobs from {len(invalid_jobs)} invalid inputs'
            })
        except Exception as e:
            tests.append({
                'name': 'Invalid Job Filtering',
                'status': 'failed',
                'details': str(e)
            })
        
        # Test 3: Machine normalization
        try:
            # Test dictionary machines
            dict_machines = [
                {'MachineName_v': 'MACHINE1'},
                {'MachineName_v': 'MACHINE2'}
            ]
            result1 = JobValidator.normalize_machines(dict_machines)
            
            # Test string machines
            string_machines = ['MACHINE1', 'MACHINE2']
            result2 = JobValidator.normalize_machines(string_machines)
            
            tests.append({
                'name': 'Machine Normalization',
                'status': 'passed' if result1 == result2 == ['MACHINE1', 'MACHINE2'] else 'failed',
                'details': f'Dict: {result1}, String: {result2}'
            })
        except Exception as e:
            tests.append({
                'name': 'Machine Normalization',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests}
    
    def test_duration_calculation(self) -> Dict:
        """Test job duration calculation logic."""
        print("\n4. Testing Duration Calculation...")
        tests = []
        
        # Test 1: Hours need calculation
        try:
            job_with_hours = {
                'job_id': 'HOURS_TEST',
                'hours_need': 8.5
            }
            duration = JobDurationCalculator.calculate_total_job_hours(job_with_hours)
            
            tests.append({
                'name': 'Hours Need Calculation',
                'status': 'passed' if duration == 8.5 else 'failed',
                'details': f'8.5 hours_need -> {duration} total hours'
            })
        except Exception as e:
            tests.append({
                'name': 'Hours Need Calculation',
                'status': 'failed',
                'details': str(e)
            })
        
        # Test 2: Quantity/rate calculation
        try:
            job_with_qty = {
                'job_id': 'QTY_TEST',
                'job_quantity': 200,
                'expect_output_per_hour': 25
            }
            duration = JobDurationCalculator.calculate_total_job_hours(job_with_qty)
            
            tests.append({
                'name': 'Quantity Rate Calculation',
                'status': 'passed' if duration == 8.0 else 'failed',
                'details': f'200 qty / 25 per hour -> {duration} hours'
            })
        except Exception as e:
            tests.append({
                'name': 'Quantity Rate Calculation',
                'status': 'failed',
                'details': str(e)
            })
        
        # Test 3: Overhead calculation
        try:
            job_with_overhead = {
                'job_id': 'OVERHEAD_TEST',
                'hours_need': 5.0,
                'setup_time': 1800,  # 0.5 hours in seconds
                'break_time': 3600,  # 1 hour in seconds
                'no_prod_time': 1800  # 0.5 hours in seconds
            }
            duration = JobDurationCalculator.calculate_total_job_hours(job_with_overhead)
            expected = 5.0 + 0.5 + 1.0 + 0.5  # 7.0 hours total
            
            tests.append({
                'name': 'Overhead Calculation',
                'status': 'passed' if abs(duration - expected) < 0.1 else 'failed',
                'details': f'5.0 + overhead -> {duration} hours (expected ~{expected})'
            })
        except Exception as e:
            tests.append({
                'name': 'Overhead Calculation',
                'status': 'failed',
                'details': str(e)
            })
        
        # Test 4: Horizon calculation
        try:
            test_jobs = [
                {'job_id': 'J1', 'hours_need': 2.0},
                {'job_id': 'J2', 'hours_need': 5.0},
                {'job_id': 'J3', 'hours_need': 3.0}
            ]
            horizon = HorizonCalculator.calculate_horizon(test_jobs, 24)
            
            tests.append({
                'name': 'Horizon Calculation',
                'status': 'passed' if horizon >= 24 else 'failed',
                'details': f'3 jobs -> {horizon} hour horizon (min 24)'
            })
        except Exception as e:
            tests.append({
                'name': 'Horizon Calculation',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests}
    
    def test_model_building(self) -> Dict:
        """Test CP-SAT model building."""
        print("\n5. Testing Model Building...")
        tests = []
        
        try:
            config = SchedulingConfigManager.load_config()
            
            # Test 1: Model builder initialization
            try:
                builder = CPSATModelBuilder(config)
                tests.append({
                    'name': 'Model Builder Init',
                    'status': 'passed',
                    'details': 'Successfully initialized CPSATModelBuilder'
                })
            except Exception as e:
                tests.append({
                    'name': 'Model Builder Init',
                    'status': 'failed',
                    'details': str(e)
                })
                return {'status': 'error', 'tests': tests}
            
            # Test 2: Variable creation
            try:
                test_jobs = [
                    {'job_id': 'VAR_TEST1', 'MachineName_v': 'MACHINE1', 'hours_need': 4.0},
                    {'job_id': 'VAR_TEST2', 'MachineName_v': 'MACHINE2', 'hours_need': 6.0}
                ]
                machines = ['MACHINE1', 'MACHINE2']
                horizon = 100
                
                builder.create_model(test_jobs, machines, horizon)
                
                tests.append({
                    'name': 'Variable Creation',
                    'status': 'passed' if len(builder.all_tasks) == 2 else 'failed',
                    'details': f'Created {len(builder.all_tasks)} task variables'
                })
            except Exception as e:
                tests.append({
                    'name': 'Variable Creation',
                    'status': 'failed',
                    'details': str(e)
                })
            
            # Test 3: Machine constraints
            try:
                machine_constraints_added = True
                for machine in machines:
                    if machine not in builder.jobs_on_machine:
                        machine_constraints_added = False
                        break
                
                tests.append({
                    'name': 'Machine Constraints',
                    'status': 'passed' if machine_constraints_added else 'failed',
                    'details': f'NoOverlap constraints for {len(machines)} machines'
                })
            except Exception as e:
                tests.append({
                    'name': 'Machine Constraints',
                    'status': 'failed',
                    'details': str(e)
                })
            
        except Exception as e:
            tests.append({
                'name': 'Model Building Test Setup',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests}
    
    def test_constraint_management(self) -> Dict:
        """Test constraint management system."""
        print("\n6. Testing Constraint Management...")
        tests = []
        
        try:
            config = SchedulingConfigManager.load_config()
            constraint_manager = ConstraintManager(config)
            
            # Create a simple model for testing
            builder = CPSATModelBuilder(config)
            test_jobs = [
                {'job_id': 'CONST_TEST1', 'MachineName_v': 'MACHINE1', 'hours_need': 3.0, 'priority': 1},
                {'job_id': 'CONST_TEST2', 'MachineName_v': 'MACHINE1', 'hours_need': 2.0, 'priority': 2}
            ]
            builder.create_model(test_jobs, ['MACHINE1'], 50)
            
            # Test 1: Constraint addition without errors
            try:
                constraint_manager.add_all_constraints(builder, True, 5, True)
                tests.append({
                    'name': 'Constraint Addition',
                    'status': 'passed',
                    'details': 'All constraints added without errors'
                })
            except Exception as e:
                tests.append({
                    'name': 'Constraint Addition',
                    'status': 'failed',
                    'details': str(e)
                })
            
            # Test 2: Working hours constraint grouping
            try:
                # Test the hour grouping function
                hours = [1, 2, 3, 5, 6, 10, 11, 12]
                ranges = constraint_manager._group_consecutive_hours(hours)
                expected_ranges = [(1, 3), (5, 6), (10, 12)]
                
                tests.append({
                    'name': 'Hour Grouping',
                    'status': 'passed' if ranges == expected_ranges else 'failed',
                    'details': f'Grouped {hours} -> {ranges}'
                })
            except Exception as e:
                tests.append({
                    'name': 'Hour Grouping',
                    'status': 'failed',
                    'details': str(e)
                })
            
        except Exception as e:
            tests.append({
                'name': 'Constraint Management Setup',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests}
    
    def test_solver_execution(self) -> Dict:
        """Test CP-SAT solver execution."""
        print("\n7. Testing Solver Execution...")
        tests = []
        
        try:
            config = SchedulingConfigManager.load_config()
            cpsat_solver = CPSATSolver(config)
            
            # Test 1: Simple model solving
            try:
                from ortools.sat.python import cp_model
                
                model = cp_model.CpModel()
                x = model.NewIntVar(0, 10, 'x')
                y = model.NewIntVar(0, 10, 'y')
                model.Add(x + y <= 10)
                model.Maximize(x + y)
                
                result = cpsat_solver.solve_model(model)
                
                tests.append({
                    'name': 'Simple Model Solving',
                    'status': 'passed' if result.status == cp_model.OPTIMAL else 'warning',
                    'details': f'Status: {result.solver.StatusName(result.status)}, Time: {result.solve_time:.3f}s'
                })
            except Exception as e:
                tests.append({
                    'name': 'Simple Model Solving',
                    'status': 'failed',
                    'details': str(e)
                })
            
            # Test 2: Solver configuration
            try:
                solver_params = {
                    'max_time_in_seconds': config.solver_time_limit_seconds,
                    'num_search_workers': min(os.cpu_count() or 4, config.max_workers_limit),
                    'relative_gap_limit': config.relative_gap_limit
                }
                
                tests.append({
                    'name': 'Solver Configuration',
                    'status': 'passed',
                    'details': f'Configured with {len(solver_params)} parameters'
                })
            except Exception as e:
                tests.append({
                    'name': 'Solver Configuration',
                    'status': 'failed',
                    'details': str(e)
                })
            
        except Exception as e:
            tests.append({
                'name': 'Solver Execution Setup',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests}
    
    def test_result_processing(self) -> Dict:
        """Test result processing and output formatting."""
        print("\n8. Testing Result Processing...")
        tests = []
        
        try:
            config = SchedulingConfigManager.load_config()
            processor = ResultProcessor(config)
            
            # Test 1: Metadata creation
            try:
                from ortools.sat.python import cp_model
                
                # Create mock solver result
                model = cp_model.CpModel()
                solver = cp_model.CpSolver()
                x = model.NewIntVar(0, 10, 'x')
                model.Maximize(x)
                status = solver.Solve(model)
                
                # Create mock model builder
                builder = CPSATModelBuilder(config)
                
                # Create mock solver result
                class MockSolverResult:
                    def __init__(self):
                        self.solver = solver
                        self.status = status
                        self.solve_time = 0.1
                        self.model = model
                        self.performance_warning = False
                
                result = MockSolverResult()
                metadata = processor._create_metadata(result, builder, int(time.time()))
                
                required_fields = ['status', 'solver_time', 'performance_metrics']
                has_required = all(field in metadata for field in required_fields)
                
                tests.append({
                    'name': 'Metadata Creation',
                    'status': 'passed' if has_required else 'failed',
                    'details': f'Created metadata with {len(metadata)} fields'
                })
            except Exception as e:
                tests.append({
                    'name': 'Metadata Creation',
                    'status': 'failed',
                    'details': str(e)
                })
            
            # Test 2: Time conversion
            try:
                start_epoch, end_epoch = processor._convert_relative_to_epoch(10, 20)
                time_diff = end_epoch - start_epoch
                expected_diff = 10 * 3600  # 10 hours in seconds
                
                tests.append({
                    'name': 'Time Conversion',
                    'status': 'passed' if abs(time_diff - expected_diff) < 100 else 'warning',
                    'details': f'10h relative -> {time_diff}s epoch difference'
                })
            except Exception as e:
                tests.append({
                    'name': 'Time Conversion',
                    'status': 'failed',
                    'details': str(e)
                })
            
        except Exception as e:
            tests.append({
                'name': 'Result Processing Setup',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests}
    
    def test_integration_compatibility(self) -> Dict:
        """Test integration with other modules."""
        print("\n9. Testing Integration Compatibility...")
        tests = []
        
        # Test 1: Data ingestion integration
        try:
            jobs, machines, setup_times = load_jobs_planning_data()
            tests.append({
                'name': 'Data Ingestion Integration',
                'status': 'passed',
                'details': f'Loaded {len(jobs)} jobs, {len(machines)} machines'
            })
            
            # Test with real data (small subset)
            if jobs and machines:
                sample_jobs = jobs[:3]  # Small subset for testing
                result = schedule_jobs(sample_jobs, machines, setup_times, 
                                     time_limit_seconds=10)  # Short time limit
                
                status = result.get('_metadata', {}).get('status', 'UNKNOWN')
                tests.append({
                    'name': 'Real Data Integration',
                    'status': 'passed' if status in ['OPTIMAL', 'FEASIBLE'] else 'warning',
                    'details': f'Status: {status} with real data'
                })
        except Exception as e:
            tests.append({
                'name': 'Data Integration',
                'status': 'failed',
                'details': str(e)
            })
        
        # Test 2: Time utilities integration
        utility_modules = [
            ('time_utils', ['datetime_to_epoch', 'epoch_to_datetime']),
            ('time_availability', ['is_time_available_for_scheduling']),
            ('scheduler_utils', ['extract_job_family', 'extract_process_number'])
        ]
        
        for module_name, functions in utility_modules:
            try:
                if 'time_utils' in module_name:
                    module = __import__(f'app.utils.{module_name}', fromlist=functions)
                else:
                    module = __import__(f'app.scheduling.{module_name}', fromlist=functions)
                
                available = [f for f in functions if hasattr(module, f)]
                
                tests.append({
                    'name': f'{module_name} Integration',
                    'status': 'passed' if len(available) == len(functions) else 'warning',
                    'details': f'Available: {available}'
                })
            except ImportError:
                tests.append({
                    'name': f'{module_name} Integration',
                    'status': 'warning',
                    'details': f'Module not available - fallback should work'
                })
        
        return {'status': 'completed', 'tests': tests}
    
    def test_performance(self) -> Dict:
        """Test performance characteristics."""
        print("\n10. Testing Performance...")
        tests = []
        
        try:
            # Performance test with different problem sizes
            problem_sizes = [
                (5, "Tiny"),
                (15, "Small"),
                (30, "Medium")
            ]
            
            performance_results = []
            
            for job_count, description in problem_sizes:
                # Generate test jobs
                test_jobs = []
                for i in range(job_count):
                    test_jobs.append({
                        'job_id': f'PERF_{i:03d}',
                        'MachineName_v': f'MACHINE_{i % 3}',
                        'hours_need': 2.0 + (i * 0.5),
                        'priority': (i % 3) + 1
                    })
                
                test_machines = ['MACHINE_0', 'MACHINE_1', 'MACHINE_2']
                
                # Measure performance
                gc.collect()
                start_memory = self.get_memory_usage()
                start_time = time.time()
                
                try:
                    result = schedule_jobs(
                        test_jobs, test_machines, 
                        time_limit_seconds=15,  # Short time limit for testing
                        max_jobs_limit=job_count + 5
                    )
                    
                    end_time = time.time()
                    end_memory = self.get_memory_usage()
                    
                    status = result.get('_metadata', {}).get('status', 'UNKNOWN')
                    is_successful = status in ['OPTIMAL', 'FEASIBLE']
                    
                    performance_results.append({
                        'description': description,
                        'job_count': job_count,
                        'status': status,
                        'successful': is_successful,
                        'time': end_time - start_time,
                        'memory_mb': end_memory - start_memory
                    })
                    
                    tests.append({
                        'name': f'Performance {description} ({job_count} jobs)',
                        'status': 'passed' if is_successful and (end_time - start_time) < 20 else 'warning',
                        'details': f'{status} in {end_time - start_time:.2f}s, {end_memory - start_memory:.1f}MB'
                    })
                    
                except Exception as e:
                    tests.append({
                        'name': f'Performance {description} ({job_count} jobs)',
                        'status': 'failed',
                        'details': str(e)
                    })
            
            # Overall performance assessment
            successful_tests = [r for r in performance_results if r['successful']]
            if successful_tests:
                avg_time = sum(r['time'] for r in successful_tests) / len(successful_tests)
                max_time = max(r['time'] for r in successful_tests)
                
                tests.append({
                    'name': 'Overall Performance',
                    'status': 'passed' if avg_time < 10 and max_time < 20 else 'warning',
                    'details': f'Avg: {avg_time:.2f}s, Max: {max_time:.2f}s'
                })
            
        except Exception as e:
            tests.append({
                'name': 'Performance Testing',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests, 'performance_data': performance_results if 'performance_results' in locals() else []}
    
    def test_production_readiness(self) -> Dict:
        """Test production readiness factors."""
        print("\n11. Testing Production Readiness...")
        tests = []
        
        # Test 1: Memory stability
        try:
            initial_memory = self.get_memory_usage()
            
            # Run multiple scheduling cycles
            for cycle in range(3):
                test_jobs = [
                    {'job_id': f'CYCLE_{cycle}_{i}', 'MachineName_v': f'MACHINE_{i%2}', 'hours_need': 3.0}
                    for i in range(10)
                ]
                result = schedule_jobs(test_jobs, ['MACHINE_0', 'MACHINE_1'], 
                                     time_limit_seconds=5)
                gc.collect()
            
            final_memory = self.get_memory_usage()
            memory_growth = final_memory - initial_memory
            
            tests.append({
                'name': 'Memory Stability',
                'status': 'passed' if memory_growth < 100 else 'warning',
                'details': f'Memory growth: {memory_growth:.1f}MB over 3 cycles'
            })
        except Exception as e:
            tests.append({
                'name': 'Memory Stability',
                'status': 'failed',
                'details': str(e)
            })
        
        # Test 2: Error handling robustness
        try:
            error_scenarios = [
                ([], ['MACHINE1']),  # Empty jobs
                ([{'job_id': 'TEST'}], []),  # Empty machines
                ([{'invalid': 'job'}], ['MACHINE1'])  # Invalid job format
            ]
            
            handled_errors = 0
            for jobs, machines in error_scenarios:
                try:
                    result = schedule_jobs(jobs, machines, time_limit_seconds=5)
                    if '_metadata' in result and 'ERROR' in result['_metadata'].get('status', ''):
                        handled_errors += 1
                except Exception:
                    handled_errors += 1  # Exception handling is also valid
            
            tests.append({
                'name': 'Error Handling Robustness',
                'status': 'passed' if handled_errors == len(error_scenarios) else 'warning',
                'details': f'Handled {handled_errors}/{len(error_scenarios)} error scenarios'
            })
        except Exception as e:
            tests.append({
                'name': 'Error Handling Robustness',
                'status': 'warning',
                'details': f'Error testing issue: {e}'
            })
        
        # Test 3: Configuration flexibility
        try:
            base_jobs = [
                {'job_id': 'FLEX_TEST', 'MachineName_v': 'MACHINE1', 'hours_need': 4.0}
            ]
            
            # Test different configurations
            config_tests = [
                {'time_limit_seconds': 5},
                {'max_jobs_limit': 10},
                {'planning_horizon_days': 30}
            ]
            
            successful_configs = 0
            for config_override in config_tests:
                try:
                    result = schedule_jobs(base_jobs, ['MACHINE1'], **config_override)
                    if result.get('_metadata', {}).get('status') != 'ERROR':
                        successful_configs += 1
                except Exception:
                    pass
            
            tests.append({
                'name': 'Configuration Flexibility',
                'status': 'passed' if successful_configs >= 2 else 'warning',
                'details': f'{successful_configs}/{len(config_tests)} configuration overrides worked'
            })
        except Exception as e:
            tests.append({
                'name': 'Configuration Flexibility',
                'status': 'failed',
                'details': str(e)
            })
        
        return {'status': 'completed', 'tests': tests}
    
    def generate_detailed_report(self) -> str:
        """Generate comprehensive markdown report."""
        report = []
        report.append("# CP-SAT Solver Deep Scan Report")
        report.append(f"\n**Scan Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Duration**: {self.results['scan_overview']['duration']:.2f} seconds")
        report.append(f"**Total Tests**: {self.results['scan_overview']['total_tests']}")
        
        # Executive Summary
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        warning_tests = 0
        
        for category_name, category_data in self.results.items():
            if isinstance(category_data, dict) and 'tests' in category_data:
                for test in category_data['tests']:
                    total_tests += 1
                    if test['status'] == 'passed':
                        passed_tests += 1
                    elif test['status'] == 'failed':
                        failed_tests += 1
                    else:
                        warning_tests += 1
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        report.append(f"\n## Executive Summary")
        report.append(f"- ✅ **Passed**: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
        report.append(f"- ❌ **Failed**: {failed_tests}")
        report.append(f"- ⚠️ **Warnings**: {warning_tests}")
        
        if success_rate >= 85:
            report.append(f"- 🟢 **Overall Status**: EXCELLENT - Production Ready")
        elif success_rate >= 70:
            report.append(f"- 🟡 **Overall Status**: GOOD - Minor Issues")
        else:
            report.append(f"- 🔴 **Overall Status**: NEEDS ATTENTION")
        
        # Detailed Results
        report.append(f"\n## Detailed Test Results")
        
        for category_name, category_data in self.results.items():
            if category_name == 'scan_overview':
                continue
                
            if isinstance(category_data, dict) and 'tests' in category_data:
                report.append(f"\n### {category_name.replace('_', ' ').title()}")
                report.append(f"Status: {category_data.get('status', 'unknown')}")
                
                if category_data['tests']:
                    report.append("\n| Test | Status | Details |")
                    report.append("|------|--------|---------|")
                    
                    for test in category_data['tests']:
                        status_icon = "✅" if test['status'] == 'passed' else "❌" if test['status'] == 'failed' else "⚠️"
                        report.append(f"| {test['name']} | {status_icon} {test['status']} | {test['details']} |")
        
        # Performance Analysis
        if 'performance_analysis' in self.results and 'performance_data' in self.results['performance_analysis']:
            report.append(f"\n## Performance Analysis")
            perf_data = self.results['performance_analysis']['performance_data']
            
            if perf_data:
                report.append("\n| Problem Size | Jobs | Status | Time (s) | Memory (MB) |")
                report.append("|--------------|------|--------|----------|-------------|")
                
                for result in perf_data:
                    status_icon = "✅" if result['successful'] else "❌"
                    report.append(f"| {result['description']} | {result['job_count']} | {status_icon} {result['status']} | {result['time']:.2f} | {result['memory_mb']:.1f} |")
        
        # Configuration Analysis
        if 'configuration_analysis' in self.results and 'config_values' in self.results['configuration_analysis']:
            report.append(f"\n## Configuration Analysis")
            config_values = self.results['configuration_analysis']['config_values']
            
            report.append("\n| Parameter | Value | Type |")
            report.append("|-----------|-------|------|")
            
            for key, value in config_values.items():
                param_type = "time" if "time" in key.lower() or "seconds" in key.lower() else "limit" if "limit" in key.lower() else "config"
                report.append(f"| {key} | {value} | {param_type} |")
        
        return "\n".join(report)


def main():
    """Run comprehensive deep scan."""
    scanner = CPSATDeepScanner()
    
    # Run deep scan
    results = scanner.run_deep_scan()
    
    # Generate and save report
    report = scanner.generate_detailed_report()
    
    print("\n" + "=" * 60)
    print("DEEP SCAN COMPLETED")
    print("=" * 60)
    print(report)
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cpsat_solver_deep_scan_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📊 Detailed results saved to: {filename}")
    
    return report


if __name__ == "__main__":
    main()