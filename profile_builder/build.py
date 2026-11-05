def build_readme(profile):
    lines = [f"# Hi, I'm {profile['name']}", "", profile["bio"], ""]

    lines += ["## Links", ""]
    for label, url in profile["links"].items():
        lines.append(f"- [{label}]({url})")
    lines.append("")

    lines += ["## Skills", "", ", ".join(profile["skills"]), ""]

    lines += ["## Featured Projects", ""]
    for project in profile["projects"]:
        lines.append(f"- [{project['name']}]({project['url']}): {project['description']}")

    return "\n".join(lines) + "\n"
