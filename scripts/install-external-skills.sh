#!/bin/sh
set -eu

# Match the public skills in mattpocock-skills' plugin manifest.
# Avoid installing the repository's misc and in-progress skills.
matt_skills='ask-matt,diagnosing-bugs,grill-with-docs,triage,improve-codebase-architecture,setup-matt-pocock-skills,tdd,to-spec,to-tickets,wayfinder,implement,implement-spec,prototype,research,domain-modeling,codebase-design,code-review,pr,retro,wizard,grill-me,grilling,handoff,teach,to-questionnaire,wait-what,writing-for-agents'
skillshare install mattpocock/skills --skill "$matt_skills" --update -g

skillshare install herdrdev/herdr/skills/herdr --update -g

skillshare install obsidianmd/obsidian-skills \
  --skill defuddle,json-canvas,knap,obsidian-bases,obsidian-cli,obsidian-headless,obsidian-markdown --update -g

skillshare sync -g
