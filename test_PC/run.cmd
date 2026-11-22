@echo off
setlocal
pushd "%~dp0.." || exit /b 1
set "suite="
if /i "%~1"=="robot" set "suite=tests.test_robot"
if /i "%~1"=="dashboard" set "suite=tests.test_dashboard"
if /i "%~1"=="console" set "suite=tests.dashboard.test_robot_console"
if /i "%~1"=="lidar" set "suite=tests.host.test_lidar tests.host.test_scan"
if /i "%~1"=="integration" set "suite=tests.dashboard.test_demo tests.robot.test_role_integration tests.host.test_hub_cloud_demo"
if /i "%~1"=="all" set "suite=discover -s tests"
if not defined suite (
    echo Usage: test_PC\run.cmd robot^|dashboard^|console^|lidar^|integration^|all
    popd
    exit /b 2
)
python -m unittest %suite%
set "result=%errorlevel%"
popd
exit /b %result%
