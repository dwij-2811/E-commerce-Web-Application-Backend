@REM git add .

@REM git commit -m "%1"

@REM git push -u origin HEAD

:: Build & Deploy the SAM application
sam build && sam deploy