# LinkedIn post (copy everything between the lines)

---

I turned off one setting on my iPhone and my own network tool flagged it as a stranger.

That's the whole point of the project. I'm learning how network anomaly detection actually works, so I built a small tool called lan-watchdog to see how it behaves on a real network, false alarms included.

Every two minutes it asks my home network "who's here?" using ARP, remembers every device it has seen, and alerts me when something new joins. A live dashboard shows what it found.

What running it on my real network taught me:
• ARP just trusts whoever answers, which is why spoofing is possible
• Phones use private Wi-Fi addresses, so one phone can look like several devices
• Detection tells you something changed, not who it is. After my iPhone test, more private-address devices appeared and I'm still tracing which are mine

It's one Docker container and a few hundred lines of Python. It's a learning project, not a security product, and the README is honest about its limits.

Next I want to handle MAC randomisation properly, add online/offline status, and send events to Azure Monitor.

I'm a Technical Support Analyst working towards network and cloud roles, and I'm open to part-time work (up to about 24 hours a week) from November. If you work in networking, I'd love your thoughts on what I've missed.

Repo in the first comment.

#Networking #Docker #Python #LearningInPublic #Cybersecurity #Melbourne

---

Before posting:
- Attach `docs/dashboard.png` (the cropped one with MAC addresses blurred). Do not use the other screenshots.
- Edit the "still tracing" line if you've identified those devices by then. A resolved version is even better: say what they turned out to be.
- Put the GitHub link in the first comment, not in the post body.
- Best time: Tuesday to Thursday morning, Melbourne time.
- When people reply, answer with a question back. The post asks for feedback, so use it.
