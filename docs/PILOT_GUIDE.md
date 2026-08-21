# ErgoVigilance — Pilot User Guide

A plain-language guide for operators, supervisors, and safety managers using
ErgoVigilance during the factory pilot. No technical jargon.

---

## What is ErgoVigilance?

An AI camera system that watches your workstation and gives you real-time feedback
on your posture. It detects when you're bending your neck too far, leaning forward,
or holding an awkward position — and warns you before it causes injury.

**It does NOT:**
- Record and store video long-term (recordings are deleted after 30 days)
- Send anything to the internet (everything stays on the factory PC)
- Track your identity unless you've signed the consent form and chosen face recognition

---

## Logging In

1. Open the browser on the factory PC (or go to `http://<PC-IP>:8080` from any device on the factory network)
2. Enter your email and password (given to you by the administrator)
3. You'll see the dashboard

**Your role determines what you can see:**

| Role | Can do | Cannot do |
|------|--------|-----------|
| **Operator** | Start/stop sessions, view own data, acknowledge alerts | See other workers' data, change settings |
| **Supervisor** | Everything an operator can + view all workers, override risk levels | Change system settings |
| **Safety Manager** | Everything a supervisor can + resolve alerts, view reports | Delete workers or change auth settings |
| **Admin** | Full access to everything | — |

---

## Starting a Monitoring Session

1. Go to **Live Monitoring** (the main dashboard)
2. Click **Start Session**
3. The camera feed will appear — check that:
   - Your full torso and arms are visible
   - Your face is not obscured
   - The lighting is even (no strong backlight)
4. A green **"Person Detected"** indicator confirms the system sees you
5. If it says **"No person detected"**, adjust your position or follow the **Setup Wizard** (gear icon)

**What you'll see while it runs:**
- **Posture status** — big text showing GOOD / CAUTION / WARNING
- **Risk score** — a number from 0-100 (lower is better)
- **Live skeleton** — colored lines showing your body position
- **Alerts** — pop-up warnings if your posture is risky (e.g., "Neck flexion high — try to keep your head more upright")

---

## During the Session

**The system will warn you if:**
- Your neck is bent forward more than 30° for too long
- Your trunk is leaning more than 60°
- Your shoulders are uneven
- You've been in a risky position for an extended time (fatigue builds up)

**What to do when you get a warning:**
1. Look at the specific recommendation on screen (e.g., "Straighten your back")
2. Adjust your position
3. The system will automatically clear the warning when your posture improves

**You can also:**
- Click **Override** to log that you disagree with a risk level (add a reason)
- Click **Capture** to take a screenshot
- Click **Log** to add a note about what you're doing (e.g., "reaching for a part")

---

## Stopping a Session

1. Click **Stop Session**
2. A summary appears showing:
   - How long the session ran
   - What percentage of time was LOW / MEDIUM / HIGH risk
   - Any alerts that fired
   - Recommendations for improvement
3. You can **export a PDF report** from this screen
4. The session is saved automatically

---

## Viewing Your History

- Go to **Session History** to see all past sessions
- Click any session to see details, trends, and the full report
- The **Reports** page lets you generate PDFs for risk trends, safety summaries, and worker-specific reports

---

## For Supervisors & Safety Managers

**Alert Management (bell icon):**
- See all active and recent alerts across all workers
- **Acknowledge** an alert to confirm you've seen it
- **Resolve** an alert to mark it as addressed
- Filter by severity (Critical, High, Info)

**Worker Management (Workers page):**
- Add new workers with name, department, and shift
- Set identity mode (face recognition, badge/QR, or anonymous)
- View consent status
- Generate QR badges for badge-scan check-in
- Delete worker data (right-to-erasure) when a worker leaves

**Reports & Analytics:**
- **Risk Trend** — how risk levels change over time (PDF/CSV/JSON)
- **Safety Report** — full safety summary (PDF)
- **Session Report** — detailed per-session breakdown (PDF)
- **Worker Trends** — compare risk patterns across workers (PDF)
- **Incident Evidence Package** — one-click zip with everything needed for OSHA/insurance review

**Manager Dashboard:**
- Factory-wide summary: total sessions, average risk, top issues
- Department-level breakdowns
- Weekly improvement trends

---

## Camera Setup (Setup Wizard)

If the camera needs repositioning:
1. Go to **Setup Wizard**
2. The system will guide you through:
   - **Framing** — ensure full torso + arms are visible
   - **Lighting** — check that your face is well-lit, not backlit
   - **Face detection** — confirm the system can see your face
3. Follow the on-screen instructions until you get green checkmarks

---

## Common Questions

**Q: Is my video being stored?**
Recordings are stored locally on the factory PC for up to 30 days, then automatically deleted. Nothing is sent to the internet.

**Q: Can I see who else is being monitored?**
Only if you're a supervisor or above. Operators see only their own sessions.

**Q: What if the system gives me a wrong alert?**
Click **Override** and explain why. This helps improve the system.

**Q: What happens if the PC crashes during a session?**
The system saves checkpoints every few minutes, so at most you lose a few minutes of data. The session can be recovered.

**Q: I'm not comfortable with face recognition.**
You can use badge/QR check-in instead, or remain anonymous. The posture safety works the same way regardless.

**Q: Can I use this on my phone?**
Yes — open `http://<PC-IP>:8080` from any browser on the factory network. The dashboard is responsive.

---

## Need Help?

Contact your on-site administrator or safety manager. For technical issues,
check that:
1. The camera is plugged in and detected
2. The browser can reach `http://<PC-IP>:8080`
3. The backend is running (check `http://<PC-IP>:8000/health`)

For persistent issues, the administrator can restart the service via
`Restart-Service ErgoVigilance` (Windows) or `docker compose restart` (Docker).
