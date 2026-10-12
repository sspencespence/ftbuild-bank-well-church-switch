[out:csv(::type,::id,name,denomination,website,"contact:website",url,"addr:postcode","addr:city";true;",")][timeout:240];
area["ISO3166-1"="GB"][admin_level=2]->.uk;
(
  nwr["amenity"="place_of_worship"]["religion"="christian"]["website"](area.uk);
  nwr["amenity"="place_of_worship"]["religion"="christian"]["contact:website"](area.uk);
  nwr["amenity"="place_of_worship"]["religion"="christian"]["url"](area.uk);
);
out center;
