// Rejouer la spec officielle de javascript/say contre l'implementation rendue
// par l'agent, SANS toucher au conteneur juge ni au repertoire du tirage.
// On importe le fichier tel quel et on compare les 16 attentes de say.spec.js.
import { say } from 'file:///C:/Users/test/tools/aider-bench/aider/tmp.benchmarks/pi_dimD2/javascript/exercises/practice/say/say.js';

const attendus = [
  [0, 'zero'],
  [1, 'one'],
  [14, 'fourteen'],
  [20, 'twenty'],
  [22, 'twenty-two'],
  [100, 'one hundred'],
  [123, 'one hundred twenty-three'],
  [1000, 'one thousand'],
  [1234, 'one thousand two hundred thirty-four'],
  [1000000, 'one million'],
  [1000002, 'one million two'],
  [1002345, 'one million two thousand three hundred forty-five'],
  [1000000000, 'one billion'],
  [987654321123,
    'nine hundred eighty-seven billion six hundred fifty-four million ' +
    'three hundred twenty-one thousand one hundred twenty-three'],
];

let ok = 0, ko = 0;
for (const [n, veut] of attendus) {
  let eu;
  try { eu = say(n); } catch (e) { eu = 'LEVE: ' + e.message; }
  if (eu === veut) { ok++; } else { ko++; console.log(`  FAIL say(${n})\n     eu   : ${JSON.stringify(eu)}\n     veut : ${JSON.stringify(veut)}`); }
}

// les deux cas d'erreur : le message EXACT est exige par toThrow(new Error(...))
const MSG = 'Number must be between 0 and 999,999,999,999.';
for (const n of [-1, 1000000000000]) {
  let msg = null;
  try { say(n); } catch (e) { msg = e.message; }
  if (msg === MSG) { ok++; } else {
    ko++;
    console.log(`  FAIL say(${n}) doit lever le message EXACT\n     eu   : ${JSON.stringify(msg)}\n     veut : ${JSON.stringify(MSG)}`);
  }
}
console.log(`\n${ok} passent, ${ko} echouent, sur ${attendus.length + 2} tests de la spec officielle.`);
