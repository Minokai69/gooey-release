// Runtime candidates are filtered by QML before reaching these pure policies.
// Never choose an output based on the cursor or registration order.
function choose(candidates, token, output) {
  if (token) {
    for (var i = 0; i < candidates.length; i++) {
      if (candidates[i].token === token) return candidates[i]
    }
    return null
  }
  var sorted = candidates.slice().sort(function(a, b) {
    if (a.output !== b.output) return a.output < b.output ? -1 : 1
    if (a.position !== b.position) return a.position < b.position ? -1 : 1
    return a.token < b.token ? -1 : (a.token > b.token ? 1 : 0)
  })
  for (var j = 0; j < sorted.length; j++) {
    if (sorted[j].output === output) return sorted[j]
  }
  return sorted.length ? sorted[0] : null
}
