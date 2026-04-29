/* Shared Firebase Auth + Realtime Database helpers for protected DayDine SaaS pages. */
(function(global){
  function fb(){
    if(!global.DayDineFirebase){ throw new Error('DayDineFirebase is not loaded.'); }
    return global.DayDineFirebase;
  }
  function auth(){ return fb().auth(); }
  function db(){ return fb().db(); }
  function p(){ return fb().path.apply(null, arguments); }
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function nextUrl(){ return new URLSearchParams(global.location.search).get('next') || ''; }
  function loginUrl(){ return '/login?next=' + encodeURIComponent(global.location.pathname + global.location.search); }
  function role(profile){ return String((profile && profile.role) || '').toLowerCase(); }
  function isActive(profile){ return !!profile && profile.active !== false; }
  function hasRole(profile, allowed){
    if(!allowed || !allowed.length) return true;
    return allowed.map(String).map(x=>x.toLowerCase()).includes(role(profile));
  }
  async function getProfile(user){
    if(!user) return null;
    const snap = await db().ref(p('users', user.uid)).once('value');
    const profile = snap.val();
    if(!profile){
      const err = new Error('Signed in, but no DayDine user profile exists for this Firebase UID. Ask an admin to add this UID under daydine_saas/users.');
      err.code = 'daydine/no-profile';
      throw err;
    }
    profile.uid = user.uid;
    profile.email = profile.email || user.email || '';
    return profile;
  }
  function renderMessage(target, title, message, actions){
    const el = typeof target === 'string' ? document.querySelector(target) : target;
    if(!el) return;
    el.innerHTML = `<section class="empty"><h1>${esc(title)}</h1><p>${esc(message)}</p>${actions||''}</section>`;
  }
  async function requireAuth(options){
    options = options || {};
    const roles = options.roles || [];
    const target = options.target || '#app';
    return new Promise(resolve=>{
      const unsub = auth().onAuthStateChanged(async user=>{
        unsub();
        if(!user){
          global.location.replace(loginUrl());
          return;
        }
        try{
          const profile = await getProfile(user);
          if(!isActive(profile)){
            await auth().signOut();
            global.location.replace('/login?inactive=1');
            return;
          }
          if(!hasRole(profile, roles)){
            renderMessage(target, 'Access not available', 'Your DayDine account does not have permission to view this area.', '<p><a class="btn" href="/client">Go to client portal</a></p>');
            return;
          }
          resolve({user, profile});
        }catch(err){
          console.error(err);
          renderMessage(target, 'Account setup needed', err.message || 'Could not load your DayDine user profile.', '<p><a class="btn" href="/login">Back to login</a></p>');
        }
      });
    });
  }
  async function signIn(email, password){
    const cred = await auth().signInWithEmailAndPassword(email, password);
    const profile = await getProfile(cred.user);
    return {user: cred.user, profile};
  }
  async function signOut(){ await auth().signOut(); global.location.replace('/login'); }
  async function resetPassword(email){ return auth().sendPasswordResetEmail(email); }
  async function canAccessVenue(profile, venueId){
    if(role(profile)==='admin') return true;
    if(profile && profile.venueIds && profile.venueIds[venueId]) return true;
    if(!profile || !profile.clientId) return false;
    const snap = await db().ref(p('clientVenueAccess', profile.clientId + '_' + venueId)).once('value');
    const access = snap.val();
    return !!access && access.active !== false;
  }
  async function venueIdsFor(profile){
    if(role(profile)==='admin'){
      const snap = await db().ref(p('venues')).once('value');
      return Object.keys(snap.val() || {});
    }
    return Object.keys((profile && profile.venueIds) || {});
  }
  async function readVenue(venueId){
    const snap = await db().ref(p('venues', venueId)).once('value');
    return snap.val();
  }
  async function readVenues(profile){
    const ids = await venueIdsFor(profile);
    const rows = await Promise.all(ids.map(async id=>({id, data: await readVenue(id)})));
    return rows.filter(x=>x.data).map(x=>Object.assign({id:x.id}, x.data));
  }
  async function readSnapshot(venueId, month){
    let targetMonth = month;
    if(!targetMonth || targetMonth === 'latest'){
      const venue = await readVenue(venueId);
      targetMonth = (venue && venue.latestSnapshotMonth) || '2026-04';
    }
    const snap = await db().ref(p('operatorDashboards', venueId, 'snapshots', targetMonth)).once('value');
    const data = snap.val();
    if(!data){
      const err = new Error('No protected dashboard snapshot exists yet for ' + venueId + ' / ' + targetMonth + '. Seed daydine_saas/operatorDashboards before using this route for clients.');
      err.code = 'daydine/no-snapshot';
      throw err;
    }
    return data;
  }
  function destinationFor(profile){
    const requested = nextUrl();
    if(requested) return requested;
    return role(profile)==='admin' ? '/admin' : '/client';
  }
  global.DayDineAuth = {requireAuth, signIn, signOut, resetPassword, getProfile, canAccessVenue, readVenues, readVenue, readSnapshot, destinationFor, esc, role};
})(window);
