/*
 * fanet-scenario-nbqmaodv.cc -- FANET scenario for the nbqmaodv routing module.
 * STEP11: the scenario body lives in fanet-core.h; this file only selects the routing helper.
 */
#include "ns3/nbqmaodv-module.h"

#include "fanet-core.h"

static std::unique_ptr<Ipv4RoutingHelper>
MakeRouting(const std::string& proto, const AttrList& attrs)
{
    if (proto == "NBQ-MAODV")
        return Make<NbqmaodvHelper>(attrs);
    NS_FATAL_ERROR("Unknown protocol: " << proto);
    return nullptr;
}

int
main(int argc, char* argv[])
{
    return FanetMain(argc, argv, "NBQ-MAODV", &MakeRouting);
}
