
import git

def get_git_commit_hash():
    repo = git.Repo(search_parent_directories=True)
    sha = repo.head.object.hexsha
    return sha