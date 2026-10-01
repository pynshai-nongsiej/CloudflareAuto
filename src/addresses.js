import { faker } from '@faker-js/faker/locale/en';

// Accepts both legacy hex-suffixed format and new clean format
export const LOCAL_PART = /^(?:[a-f0-9]{32}|[a-z]{1,20}\.[a-z]{1,20}(?:\.[a-f0-9]{12})?(?:\d{1,4})?)$/;

export function createLocalPart(clean = false) {
  const sanitize = name => name.normalize('NFKD').replace(/[^a-z]/gi, '').toLowerCase().slice(0, 20) || 'mail';
  const first = sanitize(faker.person.firstName());
  const last = sanitize(faker.person.lastName());

  if (clean) {
    // Polished format: firstname.lastname or firstname.lastname42
    // Small numeric suffix for uniqueness without the ugly hex
    const num = Math.floor(Math.random() * 100);
    return num > 0 ? `${first}.${last}${num}` : `${first}.${last}`;
  }

  // Legacy format: firstname.lastname.hexid
  const suffix = crypto.randomUUID().replaceAll('-', '').slice(0, 12);
  return `${first}.${last}.${suffix}`;
}
