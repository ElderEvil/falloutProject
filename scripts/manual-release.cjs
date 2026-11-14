// Semantic Release still calculates and publishes the version; this selects the bump.
exports.analyzeCommits = (_config, { env }) => {
  const type = env.RELEASE_AS
  if (!['patch', 'minor', 'major'].includes(type)) {
    throw new Error('Manual release requires RELEASE_AS=patch, minor, or major')
  }
  return type
}
