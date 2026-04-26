/* DayDine UK-wide location autocomplete
   Enhances UK lookup inputs without changing the existing search pipeline.
   Static suggestions cover major UK towns/cities and local authorities.
   Dynamic suggestions use postcodes.io place search as the user types. */
(function(){
  const INPUT_IDS=['fLocation'];
  const STATIC_LOCATIONS=[
    'United Kingdom','England','Scotland','Wales','Northern Ireland',
    'London','Greater London','Central London','City of London','Westminster','Camden','Islington','Hackney','Tower Hamlets','Southwark','Lambeth','Kensington and Chelsea','Hammersmith and Fulham','Wandsworth','Lewisham','Greenwich','Newham','Haringey','Brent','Ealing','Hounslow','Richmond upon Thames','Merton','Croydon','Bromley','Bexley','Havering','Barking and Dagenham','Redbridge','Waltham Forest','Enfield','Barnet','Harrow','Hillingdon','Kingston upon Thames','Sutton',
    'Birmingham','Manchester','Liverpool','Leeds','Sheffield','Bristol','Newcastle upon Tyne','Nottingham','Leicester','Coventry','Bradford','Wolverhampton','Solihull','Walsall','Dudley','Sandwell','Stoke-on-Trent','Derby','Hull','Kingston upon Hull','York','Doncaster','Wakefield','Rotherham','Barnsley','Huddersfield','Halifax','Blackpool','Preston','Bolton','Bury','Oldham','Rochdale','Stockport','Salford','Wigan','Warrington','Chester','Crewe','Macclesfield','Blackburn','Burnley','Lancaster','Carlisle','Middlesbrough','Sunderland','Durham','Darlington','Harrogate','Scarborough','Lincoln','Grimsby','Scunthorpe','Mansfield','Chesterfield','Peterborough','Norwich','Ipswich','Cambridge','Oxford','Reading','Milton Keynes','Northampton','Luton','Bedford','Aylesbury','High Wycombe','Slough','Watford','St Albans','Hemel Hempstead','Stevenage','Chelmsford','Colchester','Southend-on-Sea','Basildon','Harlow','Maidstone','Canterbury','Dover','Ashford','Medway','Rochester','Gillingham','Dartford','Brighton','Brighton and Hove','Hove','Eastbourne','Hastings','Crawley','Worthing','Chichester','Portsmouth','Southampton','Winchester','Bournemouth','Poole','Christchurch','Dorset','Salisbury','Swindon','Gloucester','Cheltenham','Worcester','Hereford','Shrewsbury','Telford','Stafford','Lichfield','Tamworth','Nuneaton','Rugby','Warwick','Warwick District','Leamington Spa','Royal Leamington Spa','Stratford-upon-Avon','Stratford upon Avon','Stratford on Avon','Kenilworth','Coventry','Bicester','Banbury','Chelmsley Wood','Redditch','Bromsgrove','Kidderminster','Evesham','Malvern','Bath','Exeter','Plymouth','Torquay','Paignton','Truro','Falmouth','St Ives','Newquay','Taunton','Yeovil','Weston-super-Mare','Glasgow','Edinburgh','Aberdeen','Dundee','Inverness','Perth','Stirling','Paisley','East Kilbride','Hamilton','Motherwell','Ayr','Kilmarnock','Dumfries','Cardiff','Swansea','Newport','Wrexham','Bangor','Aberystwyth','Llandudno','Barry','Bridgend','Merthyr Tydfil','Carmarthen','Belfast','Derry','Londonderry','Lisburn','Newry','Armagh','Bangor Northern Ireland','Craigavon','Antrim','Ballymena','Coleraine','Omagh','Enniskillen',
    'CV37','CV32','CV31','B1','B2','B3','B4','M1','M2','L1','LS1','S1','BS1','NE1','NG1','LE1','SW1','W1','EC1','WC1','E1','SE1','N1','NW1'
  ];
  const seen=new Set();
  const normalise=value=>String(value||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  function addOption(datalist,value){
    value=String(value||'').trim();
    if(!value)return;
    const key=normalise(value);
    if(!key||seen.has(key))return;
    seen.add(key);
    const option=document.createElement('option');
    option.value=value;
    datalist.appendChild(option);
  }
  function ensureDatalist(input){
    let listId=input.getAttribute('list');
    let datalist=listId&&document.getElementById(listId);
    if(!datalist){
      listId='ukLocationOptions';
      datalist=document.getElementById(listId)||document.createElement('datalist');
      datalist.id=listId;
      document.body.appendChild(datalist);
      input.setAttribute('list',listId);
    }
    return datalist;
  }
  function hydrateStatic(datalist){
    STATIC_LOCATIONS.forEach(value=>addOption(datalist,value));
  }
  function valuesFromPlace(place){
    const values=[];
    ['name_1','name_2','name_3','county_unitary','admin_district','district_borough','region','country'].forEach(key=>{
      if(place&&place[key])values.push(place[key]);
    });
    return values;
  }
  function attach(input){
    const datalist=ensureDatalist(input);
    hydrateStatic(datalist);
    let timer=null;
    input.addEventListener('input',function(){
      const q=input.value.trim();
      clearTimeout(timer);
      if(q.length<2)return;
      timer=setTimeout(async function(){
        try{
          const response=await fetch('https://api.postcodes.io/places?q='+encodeURIComponent(q)+'&limit=12');
          if(!response.ok)return;
          const payload=await response.json();
          (payload.result||[]).forEach(place=>valuesFromPlace(place).forEach(value=>addOption(datalist,value)));
        }catch(err){
          // Autocomplete is progressive enhancement only; manual town/postcode search still works.
        }
      },180);
    });
  }
  function init(){
    INPUT_IDS.map(id=>document.getElementById(id)).filter(Boolean).forEach(attach);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
