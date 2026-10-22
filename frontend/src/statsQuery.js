/** Query helpers for GET /stats/* (subset of leaderboard filters). */

export function defaultStatsFilters() {
  return {
    period: 'alltime',
    game: 'all',
    playMode: '',
    dateFrom: '',
    dateTo: '',
    includeArchived: false,
  }
}

/**
 * @param {ReturnType<typeof defaultStatsFilters>} filters
 * @param {{ includeGame?: boolean }} opts
 */
export function buildStatsQuery(filters, { includeGame = true } = {}) {
  const params = new URLSearchParams()
  params.set('period', filters.period || 'alltime')
  if (includeGame) params.set('game', filters.game || 'all')
  if (filters.playMode) params.set('play_mode', filters.playMode)
  if (filters.dateFrom) params.set('date_from', filters.dateFrom)
  if (filters.dateTo) params.set('date_to', filters.dateTo)
  if (filters.includeArchived) params.set('include_archived', 'true')
  return params.toString()
}

export function buildTournamentStatsQuery(filters) {
  const params = new URLSearchParams()
  params.set('period', filters.period || 'alltime')
  params.set('game', filters.game || 'all')
  return params.toString()
}
