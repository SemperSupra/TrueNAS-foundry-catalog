'use strict';
let bearer = null;
const status = document.getElementById('status');
const catalog = document.getElementById('catalog');
const input = document.getElementById('token');
const connect = document.getElementById('connect');
const clear = document.getElementById('clear');
async function refresh() {
  catalog.replaceChildren();
  status.textContent = 'Loading read-only catalog…';
  try {
    const response = await fetch('/v0/catalog/apps', {headers: {'Authorization': 'Bearer ' + bearer},cache: 'no-store',credentials:'omit'});
    if (!response.ok) throw Error('Catalog read denied (HTTP ' + response.status + ')');
    const data = await response.json();
    if (!Array.isArray(data.apps)) throw Error('Invalid source response');
    for (const app of data.apps) {
      const card = document.createElement('article');
      const title = document.createElement('h3'); title.textContent = app.package_id + ' @ ' + app.version;
      const source = document.createElement('p'); source.textContent = 'Revision: ' + app.source_revision;
      const digest = document.createElement('code'); digest.textContent = app.source_tree_sha256;
      const flag = document.createElement('p'); flag.textContent = 'Status: ' + app.admission + ' (not install-qualified)';
      card.append(title,source,digest,flag); catalog.appendChild(card);
    }
    status.textContent = data.apps.length + ' sources listed. Read-only.';
  } catch (e) {
    bearer = null; catalog.replaceChildren(); status.textContent = e.message;
  }
}
connect.addEventListener('click', () => {
  const value = input.value;
  input.value = '';
  if (value.length < 32) {status.textContent = 'Enter your read-only token'; return;}
  bearer = value; refresh();
});
clear.addEventListener('click', () => {bearer = null; input.value = ''; catalog.replaceChildren(); status.textContent = 'Disconnected';});
