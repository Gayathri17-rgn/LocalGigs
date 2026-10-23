# LocalGigsAgent — local prototype

A small Java + HTML/CSS/JavaScript demo for browsing local gigs, posting a gig, submitting an application, and updating application status.

## Requirements
- JDK 21 (or a recent JDK that includes `jdk.httpserver`)
- VS Code or another editor
- No Maven, Gradle, or external Java libraries required

## Run on Windows (PowerShell)
Open a terminal in the `LocalGigsAgent` root folder and run:

```powershell
javac -d out src\LocalGigsServer.java
java -cp out LocalGigsServer
```

Then open **http://localhost:8080** in your browser. Keep the terminal running while you use the website. Press `Ctrl+C` in the terminal to stop the server.

## Demo workflow
1. Browse gigs under **Find Gigs**.
2. Click **View & apply**, enter a name and age, and submit.
3. Open **Organizer Dashboard** to shortlist, accept, or reject the application.
4. Post a new gig and return to **Find Gigs** to see it.

## Important limitations
- This is a local prototype, not a production service. Data is held in memory and resets when the server stops.
- There is no authentication, database, organization verification, payment handling, or real identity verification.
- The eligibility label is a simple minimum-age rule for demonstration. The `/api/decisions/evaluate` endpoint is also a demo rule and **does not call Strands Decider 2B or Amazon Bedrock**. Do not claim actual model integration until it has been implemented and tested.
- This demo restricts applicant age to 18+ and defaults new listings to a minimum age of 18. Legal requirements must be checked before supporting any minor-focused work.
- Do not expose API keys in frontend JavaScript, commit them to GitHub, or paste them into public screenshots.
