const fold = value => value.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "");

function matchCase(word, replacement, canonical) {
  if (word === word.toUpperCase()) return replacement.toUpperCase();
  if (word[0] !== word[0].toLowerCase()) return canonical || replacement[0].toUpperCase() + replacement.slice(1);
  return replacement;
}

export function createSpelling(entries, distance, knownTerm) {
  const buckets = new Map();
  for (const [word, frequency, canonical] of entries) {
    if (!buckets.has(word.length)) buckets.set(word.length, []);
    buckets.get(word.length).push({ word, frequency, canonical });
  }

  return query => {
    if (query.length > 256) return [];
    const tokens = [...query.matchAll(/[\p{L}\p{N}_]+/gu)];
    if (tokens.length > 12) return [];
    let unknown = 0;
    let beam = [{ text: "", end: 0, edits: 0, weight: 0 }];
    for (const token of tokens) {
      const original = token[0];
      const word = fold(original);
      let options = [{ text: original, edits: 0, weight: 0 }];
      if (!knownTerm(word) && /^[\p{L}_]{4,48}$/u.test(word)) {
        if (++unknown > 2) return [];
        const limit = word.length >= 8 ? 2 : 1;
        options = [];
        for (let length = word.length - limit; length <= word.length + limit; length++) {
          for (const entry of buckets.get(length) || []) {
            const edits = distance(word, entry.word);
            if (edits > limit || !edits) continue;
            options.push({ text: matchCase(original, entry.word, entry.canonical), edits,
              weight: Math.log1p(entry.frequency) });
          }
        }
        options.sort((a, b) => a.edits - b.edits || b.weight - a.weight || a.text.localeCompare(b.text));
        options = options.slice(0, 4);
        if (!options.length) return [];
      }
      // A bounded beam supports two misspelled words without exploding the
      // candidate count, and leaves punctuation and valid API components intact.
      beam = beam.flatMap(candidate => options.map(option => ({
        text: candidate.text + query.slice(candidate.end, token.index) + option.text,
        end: token.index + original.length,
        edits: candidate.edits + option.edits,
        weight: candidate.weight + option.weight,
      }))).filter(candidate => candidate.edits <= 2)
        .sort((a, b) => a.edits - b.edits || b.weight - a.weight || a.text.localeCompare(b.text))
        .slice(0, 6);
    }
    return [...new Set(beam.filter(candidate => candidate.edits > 0)
      .map(candidate => candidate.text + query.slice(candidate.end)))];
  };
}
