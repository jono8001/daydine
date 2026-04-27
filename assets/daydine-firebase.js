/* DayDine shared Firebase bootstrap.
   Public Firebase config is not a secret. Private access must be enforced by
   Firebase Auth + Realtime Database / Firestore security rules. */
(function(global){
  const config = {
    apiKey: "AIzaSyBiFeN9DeiNnDFdu3O4uVTILnQANYsLdkA",
    authDomain: "recursive-research-eu.firebaseapp.com",
    databaseURL: "https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app",
    projectId: "recursive-research-eu",
    storageBucket: "recursive-research-eu.firebasestorage.app",
    messagingSenderId: "205357382117",
    appId: "1:205357382117:web:5b01c86ed33572abce170c"
  };

  function ensureFirebase(){
    if(!global.firebase){
      throw new Error('Firebase SDK is not loaded. Include firebase-app-compat.js before daydine-firebase.js.');
    }
    if(!global.firebase.apps.length){
      global.firebase.initializeApp(config);
    }
    return global.firebase;
  }

  global.DayDineFirebase = {
    config,
    ensureFirebase,
    auth(){ return ensureFirebase().auth(); },
    db(){ return ensureFirebase().database(); }
  };
})(window);
