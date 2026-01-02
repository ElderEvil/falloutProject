const data = require('./lighthouse.json');

console.log('=== LIGHTHOUSE SCORES ===\n');
console.log('Performance:', data.categories.performance.score);
console.log('Accessibility:', data.categories.accessibility.score);
console.log('Best Practices:', data.categories['best-practices'].score);
console.log('SEO:', data.categories.seo.score);

console.log('\n=== FAILING PERFORMANCE AUDITS (score < 0.9) ===\n');
const audits = data.audits;
Object.keys(audits).forEach(key => {
  const audit = audits[key];
  if (audit.score !== null && audit.score < 0.9 && audit.score >= 0 && audit.scoreDisplayMode === 'numeric') {
    console.log(`${audit.id}: ${audit.score} - ${audit.title}`);
    if (audit.displayValue) {
      console.log(`  Value: ${audit.displayValue}`);
    }
  }
});

console.log('\n=== ACCESSIBILITY ISSUES ===\n');
Object.keys(audits).forEach(key => {
  const audit = audits[key];
  if (audit.score === 0 && key.includes('aria') || key.includes('color-contrast') || key.includes('label')) {
    console.log(`${audit.id}: FAILED - ${audit.title}`);
    if (audit.details && audit.details.items && audit.details.items.length > 0) {
      console.log(`  ${audit.details.items.length} issues found`);
    }
  }
});
