[out:csv(::type,::id,name,denomination,religion,amenity,building,website,"contact:website",url,"addr:postcode","addr:city",::lat,::lon;true;",")][timeout:300];
area["ISO3166-1"="GB"][admin_level=2]->.uk;
(
  nwr["amenity"="place_of_worship"]["religion"="christian"](area.uk);
  nwr["building"~"^(church|chapel|cathedral)$"][!"amenity"](area.uk);
);
out center;
