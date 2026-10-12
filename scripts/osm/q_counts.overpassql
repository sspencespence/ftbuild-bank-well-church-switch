[out:json][timeout:240];
area["ISO3166-1"="GB"][admin_level=2]->.uk;
nwr["amenity"="place_of_worship"]["religion"="christian"](area.uk)->.all;
.all out count;
nwr.all["website"]->.w; .w out count;
nwr["building"="church"][!"amenity"](area.uk)->.b; .b out count;
