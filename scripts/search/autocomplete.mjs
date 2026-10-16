export function createAutocomplete(entries) {
  const names = entries.map(([name, symbol]) => ({
    name, symbol, lower: name.toLowerCase(), qualified: symbol.toLowerCase(),
    member: name.split(".").at(-1).toLowerCase(),
  }));
  return query => {
    const prefix = query.trim().replace(/::/g, ".").toLowerCase();
    if (prefix.length < 2 || prefix.length > 128 || !/^[a-z_][a-z0-9_.]*$/.test(prefix)) return [];
    if (names.some(entry => entry.lower === prefix || entry.qualified === prefix)) return [];
    const matches = [];
    for (const entry of names) {
      const qualified = prefix.startsWith("symbolica.");
      const memberQuery = !prefix.includes(".");
      // A class prefix must not crowd out matching methods on other classes.
      const rank = memberQuery && entry.member === prefix ? 0 :
        entry.lower.startsWith(prefix) ? (memberQuery && entry.lower.includes(".") ? 3 : 1) :
        entry.qualified.startsWith(prefix) ? 1 : memberQuery && entry.member.startsWith(prefix) ? 2 : -1;
      if (rank >= 0) matches.push({ name: qualified ? entry.symbol : entry.name, rank });
    }
    matches.sort((a, b) => a.rank - b.rank || a.name.length - b.name.length ||
      (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    return [...new Set(matches.map(match => match.name))].slice(0, 5);
  };
}
