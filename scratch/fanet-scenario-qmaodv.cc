/*
 * fanet-scenario-qmaodv.cc -- FANET scenario for the qmaodv routing module.
 * STEP11: the scenario body lives in fanet-core.h; this file only selects the routing helper.
 */
#include "ns3/qmaodv-module.h"

#include "fanet-core.h"

static std::unique_ptr<Ipv4RoutingHelper>
MakeRouting(const std::string& proto, const AttrList& attrs)
{
    if (proto == "QMAODV")
        return Make<QmaodvHelper>(attrs);
    if (proto == "PMAODV") // STEP7: PMAODV = shared multipath AODV core + probabilistic policy
    {
        AttrList a = attrs;
        a.insert(a.begin(), {"Policy", "Probabilistic"});
        return Make<QmaodvHelper>(a);
    }
    NS_FATAL_ERROR("Unknown protocol: " << proto);
    return nullptr;
}

int
main(int argc, char* argv[])
{
    return FanetMain(argc, argv, "QMAODV", &MakeRouting);
}
