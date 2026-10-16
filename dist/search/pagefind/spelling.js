/*! damerau-levenshtein 1.0.8
BSD 2-Clause License

Copyright (c) 2018, Tadeusz Łazurski
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/
const module = {exports: {}};
// TheSpanishInquisition

// Cache the matrix. Note that if you not pass a limit this implementation will use a dynamically calculate one.

module.exports = function(__this, that, limit) {

  var thisLength = __this.length,
      thatLength = that.length,
      matrix = [];

  // If the limit is not defined it will be calculate from this and that args.
  limit = (limit || ((thatLength > thisLength ? thatLength : thisLength)))+1;

  for (var i = 0; i < limit; i++) {
    matrix[i] = [i];
    matrix[i].length = limit;
  }
  for (i = 0; i < limit; i++) {
    matrix[0][i] = i;
  }

  if (Math.abs(thisLength - thatLength) > (limit || 100)){
    return prepare (limit || 100);
  }
  if (thisLength === 0){
    return prepare (thatLength);
  }
  if (thatLength === 0){
    return prepare (thisLength);
  }

  // Calculate matrix.
  var j, this_i, that_j, cost, min, t;
  for (i = 1; i <= thisLength; ++i) {
    this_i = __this[i-1];

    // Step 4
    for (j = 1; j <= thatLength; ++j) {
      // Check the jagged ld total so far
      if (i === j && matrix[i][j] > 4) return prepare (thisLength);

      that_j = that[j-1];
      cost = (this_i === that_j) ? 0 : 1; // Step 5
      // Calculate the minimum (much faster than Math.min(...)).
      min    = matrix[i - 1][j    ] + 1; // Deletion.
      if ((t = matrix[i    ][j - 1] + 1   ) < min) min = t;   // Insertion.
      if ((t = matrix[i - 1][j - 1] + cost) < min) min = t;   // Substitution.

      // Update matrix.
      matrix[i][j] = (i > 1 && j > 1 && this_i === that[j-2] && __this[i-2] === that_j && (t = matrix[i-2][j-2]+cost) < min) ? t : min; // Transposition.
    }
  }

  return prepare (matrix[thisLength][thatLength]);

/**
 *
 */
  function prepare(steps) {
    var length = Math.max(thisLength, thatLength)
    var relative = length === 0
      ? 0
      : (steps / length);
    var similarity = 1 - relative
    return {
      steps: steps,
      relative: relative,
      similarity: similarity
    };
  }

};

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

export const spellingDistance = (a, b) => module.exports(a, b).steps;
